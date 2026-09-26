"""Concept -> XBRL fact resolution. Deterministic, no LLM anywhere in this
path: 'revenue' is not one XBRL tag, so we walk fact_aliases by priority
until one resolves for the given company/period.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from stance.contracts import FactNotFound


def resolve_fact(
    engine: Engine, concept: str, cik: str, fiscal_year: int, fiscal_period: str = "FY"
) -> dict:
    """Returns the resolved fact row as a dict, or raises FactNotFound.

    Tries company-specific aliases first (cik = the company), then
    company-agnostic aliases (cik IS NULL), in priority order. This is what
    lets one company's real tag ('Revenues') differ from another's
    ('RevenueFromContractWithCustomerExcludingAssessedTax') without any
    model guessing which one applies.
    """
    with engine.connect() as conn:
        aliases = conn.execute(
            text(
                "SELECT element_name FROM fact_aliases "
                "WHERE concept = :concept AND (cik = :cik OR cik IS NULL) "
                "ORDER BY (cik IS NULL), priority"
            ),
            {"concept": concept, "cik": cik},
        ).fetchall()

        if not aliases:
            raise FactNotFound(f"no alias registered for concept '{concept}'")

        for (element_name,) in aliases:
            row = conn.execute(
                text(
                    "SELECT fact_id, accession_no, cik, element_name, label, value, unit, "
                    "period_type, period_start, period_end, fiscal_year, fiscal_period, source_url "
                    "FROM xbrl_facts "
                    "WHERE cik = :cik AND element_name = :element_name "
                    "AND fiscal_year = :fiscal_year AND fiscal_period = :fiscal_period "
                    "AND segment_axis IS NULL "
                    "LIMIT 1"
                ),
                {
                    "cik": cik,
                    "element_name": element_name,
                    "fiscal_year": fiscal_year,
                    "fiscal_period": fiscal_period,
                },
            ).mappings().first()
            if row:
                return dict(row)

    raise FactNotFound(
        f"concept '{concept}' unresolved for cik={cik}, FY{fiscal_year} {fiscal_period} "
        f"— tried tags: {[a[0] for a in aliases]}"
    )


def fetch_fact_by_id(engine: Engine, fact_id: str) -> dict:
    """Direct lookup by fact_id — used by the verifier to re-derive a
    previously-cited figure, and by the sandbox executor to resolve
    ComputationSpec operands."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT fact_id, accession_no, cik, element_name, label, value, unit, "
                "period_type, period_start, period_end, fiscal_year, fiscal_period, source_url "
                "FROM xbrl_facts WHERE fact_id = :fact_id"
            ),
            {"fact_id": fact_id},
        ).mappings().first()
    if not row:
        raise FactNotFound(f"fact_id '{fact_id}' does not exist in xbrl_facts")
    return dict(row)
