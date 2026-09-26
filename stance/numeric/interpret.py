"""Maps a numeric sub-question's phrasing to a concept + optional
operation, via keyword matching — deliberately not an LLM call. This keeps
the promise that no numeric step, in either the fast or full path, ever
lets a model decide what a figure is; only word-matching against a fixed,
auditable vocabulary decides it.
"""
from __future__ import annotations

from sqlalchemy.engine import Engine

from stance.agents.writer import format_fast_path_answer
from stance.numeric.calculator import build_growth_rate_spec, build_margin_spec
from stance.numeric.executor import execute_spec
from stance.numeric.resolver import resolve_fact

_CONCEPT_KEYWORDS: dict[str, list[str]] = {
    "revenue": ["revenue", "sales", "top line"],
    "net_income": ["net income", "profit", "earnings"],
    "total_assets": ["total assets", "assets"],
    "operating_income": ["operating income", "operating margin"],
    "eps_diluted": ["eps", "earnings per share"],
}

_GROWTH_KEYWORDS = ["growth", "grew", "increase", "yoy", "year over year", "year-over-year"]
_MARGIN_KEYWORDS = ["margin"]


def detect_concept(sub_question: str) -> str:
    q = sub_question.lower()
    for concept, keywords in _CONCEPT_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return concept
    return "revenue"  # default — the most common numeric ask at this scale


def detect_operation(sub_question: str) -> str | None:
    q = sub_question.lower()
    if any(kw in q for kw in _GROWTH_KEYWORDS):
        return "growth_rate"
    if any(kw in q for kw in _MARGIN_KEYWORDS):
        return "margin"
    return None  # a plain lookup, not a computation


def answer_numeric_step(engine: Engine, sub_question: str, cik: str, fiscal_years: list[int]) -> tuple[str, list[str]]:
    """Returns (formatted answer text with citation, [fact_ids used]).
    Raises FactNotFound if a required fact is absent — the caller must let
    this propagate as a loud failure, not swallow it into a guess."""
    concept = detect_concept(sub_question)
    operation = detect_operation(sub_question)
    latest_year = max(fiscal_years)

    if operation is None or len(fiscal_years) < 2:
        fact = resolve_fact(engine, concept, cik, latest_year)
        return format_fast_path_answer(concept, fact), [fact["fact_id"]]

    prior_year = sorted(fiscal_years)[-2]
    current_fact = resolve_fact(engine, concept, cik, latest_year)
    prior_fact = resolve_fact(engine, concept, cik, prior_year)

    if operation == "growth_rate":
        spec = build_growth_rate_spec(current_fact["fact_id"], prior_fact["fact_id"])
    else:  # margin: numerator = operating_income, denominator = revenue of the same year
        numerator_fact = resolve_fact(engine, "operating_income", cik, latest_year)
        spec = build_margin_spec(numerator_fact["fact_id"], current_fact["fact_id"])
        current_fact = numerator_fact  # so its fact_id is included below

    value = execute_spec(engine, spec)
    answer = (
        f"{concept.replace('_', ' ').title()} {operation.replace('_', ' ')} "
        f"FY{prior_year}→FY{latest_year}: {value}% "
        f"[fact_id={current_fact['fact_id']}] [fact_id={prior_fact['fact_id']}]"
    )
    return answer, [current_fact["fact_id"], prior_fact["fact_id"]]
