"""The calculator agent: given a numeric sub-question and already-resolved
facts, emit a ComputationSpec. It never touches a raw numeric value —
it only ever references fact_ids. Execution happens later, in sandbox.py.
"""
from __future__ import annotations

from stance.contracts import ComputationSpec, Operand

# Maps a small set of recognised question shapes to an operation + operand
# roles. This is deliberately simple pattern matching, not an LLM call —
# the calculator's *job* is to be auditable, not clever. A more elaborate
# version could route through a small model to pick the operation, but the
# output schema (ComputationSpec) stays identical either way.


def build_growth_rate_spec(current_fact_id: str, prior_fact_id: str) -> ComputationSpec:
    return ComputationSpec(
        operation="growth_rate",
        operands=[
            Operand(role="current", fact_id=current_fact_id),
            Operand(role="prior", fact_id=prior_fact_id),
        ],
        output_unit="percent",
    )


def build_margin_spec(numerator_fact_id: str, denominator_fact_id: str) -> ComputationSpec:
    return ComputationSpec(
        operation="margin",
        operands=[
            Operand(role="numerator", fact_id=numerator_fact_id),
            Operand(role="denominator", fact_id=denominator_fact_id),
        ],
        output_unit="percent",
    )


def build_yoy_delta_spec(current_fact_id: str, prior_fact_id: str) -> ComputationSpec:
    return ComputationSpec(
        operation="yoy_delta",
        operands=[
            Operand(role="current", fact_id=current_fact_id),
            Operand(role="prior", fact_id=prior_fact_id),
        ],
        output_unit="usd",
    )


def build_ratio_spec(numerator_fact_id: str, denominator_fact_id: str) -> ComputationSpec:
    return ComputationSpec(
        operation="ratio",
        operands=[
            Operand(role="numerator", fact_id=numerator_fact_id),
            Operand(role="denominator", fact_id=denominator_fact_id),
        ],
        output_unit="ratio",
    )
