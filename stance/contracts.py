"""Typed contracts passed between agents.

These are the audit trail: every agent boundary in the graph is a Pydantic
model, not free text. In particular, ComputationSpec has no numeric output
field — the calculator agent is structurally incapable of emitting a number.
"""
from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class Scope(BaseModel):
    """Resolved entities and periods. Produced deterministically (no LLM)
    by the intake/scope agent."""

    ciks: list[str]
    tickers: list[str]
    fiscal_years: list[int]
    form_types: list[str] = Field(default_factory=lambda: ["10-K"])
    item_codes: list[str] | None = None  # e.g. ["1A"] to scope narrative retrieval


class PlanStep(BaseModel):
    step_id: str = Field(default_factory=lambda: f"s-{uuid4().hex[:8]}")
    sub_question: str
    kind: Literal["narrative", "numeric"]
    scope: Scope
    depends_on: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    question: str
    steps: list[PlanStep]


class Operand(BaseModel):
    """One input to a computation. Exactly one of fact_id / spec_id is set:
    a leaf operand points at a resolved XBRL fact, a nested operand points
    at another ComputationSpec's result."""

    role: str  # e.g. "current", "prior", "numerator", "denominator"
    fact_id: str | None = None
    spec_id: str | None = None


class ComputationSpec(BaseModel):
    """What the calculator agent emits. Note: no numeric field exists on
    this model — it cannot type a value into the output even if a model
    tried, because the schema has no place to put one."""

    spec_id: str = Field(default_factory=lambda: f"spec-{uuid4().hex[:8]}")
    operation: Literal[
        "sum", "difference", "ratio", "growth_rate", "margin", "cagr",
        "per_share", "yoy_delta",
    ]
    operands: list[Operand]
    output_unit: Literal["usd", "percent", "ratio", "usd_per_share"]
    rounding: int = 2


class RejectedFigure(BaseModel):
    claimed_value: str
    reason: Literal["no_fact_id", "value_mismatch", "unresolvable_citation"]
    detail: str = ""


class VerifierReport(BaseModel):
    figures_checked: int
    figures_traced: int
    figures_rejected: int
    citation_coverage: float  # fraction of assertions with a resolving citation
    rejected_details: list[RejectedFigure] = Field(default_factory=list)


class FactNotFound(Exception):
    """Raised by the resolver/sandbox when a required fact is absent.
    This is a feature: the system fails loudly instead of estimating."""


class UnitMismatchError(Exception):
    """Raised by the sandbox when an operation mixes incompatible units
    or period types (e.g. USD duration vs. shares instant)."""
