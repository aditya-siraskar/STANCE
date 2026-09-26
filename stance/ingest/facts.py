"""Extract XBRL facts from a company's `companyfacts` JSON (EDGAR's
per-company XBRL API) into rows for the xbrl_facts table — one row per
tagged figure, with a traceable fact_id.

Only facts for elements we actually alias (see stance/seed.py) and only
annual (form 10-K, fp FY) facts for the target fiscal years are extracted —
this keeps the fact table small and every row purposeful.
"""
from __future__ import annotations

import hashlib

from sqlalchemy import text
from sqlalchemy.engine import Engine

# us-gaap is where every concept in FACT_ALIASES lives for this project's
# watchlist; dei/other taxonomies are out of scope at this scale.
TAXONOMY = "us-gaap"


def extract_facts(
    company_facts: dict,
    cik: str,
    element_names: list[str],
    target_fiscal_years: list[int],
    form_type: str = "10-K",
    fiscal_period: str = "FY",
) -> list[dict]:
    """Walk companyfacts[TAXONOMY][element][units][unit][] entries and keep
    only those matching our form/period/year filter. Deduplicates by
    (element_name, fiscal_year, unit) keeping the entry with an accession
    number (a fact without one cannot be cited, so it is worthless here).
    """
    taxonomy_facts = company_facts.get("facts", {}).get(TAXONOMY, {})
    rows: dict[tuple, dict] = {}

    for element_name in element_names:
        element = taxonomy_facts.get(element_name)
        if not element:
            continue
        for unit, entries in element.get("units", {}).items():
            for entry in entries:
                if entry.get("form") != form_type:
                    continue
                if entry.get("fp") != fiscal_period:
                    continue
                fy = entry.get("fy")
                if fy not in target_fiscal_years:
                    continue
                accession_no = entry.get("accn")
                if not accession_no:
                    continue

                period_type = "duration" if "start" in entry else "instant"
                key = (element_name, fy, unit)
                # Deterministic fact_id (not random) so re-ingesting the same
                # accession/element/year/unit is a true no-op via ON CONFLICT,
                # matching the "idempotent by accession number" invariant.
                fact_id = "fact-" + hashlib.sha1(
                    f"{accession_no}|{element_name}|{fy}|{unit}".encode()
                ).hexdigest()[:16]
                rows[key] = {
                    "fact_id": fact_id,
                    "accession_no": accession_no,
                    "cik": cik,
                    "element_name": element_name,
                    "label": element.get("label", element_name),
                    "value": entry["val"],
                    "unit": normalise_unit(unit),
                    "period_type": period_type,
                    "period_start": entry.get("start"),
                    "period_end": entry.get("end"),
                    "fiscal_year": fy,
                    "fiscal_period": fiscal_period,
                    "source_url": (
                        f"https://www.sec.gov/cgi-bin/viewer?action=view"
                        f"&cik={int(cik)}&accession_number={accession_no}"
                    ),
                }
    return list(rows.values())


def normalise_unit(xbrl_unit: str) -> str:
    """XBRL units use e.g. 'USD', 'USD-per-shares', 'shares' — normalise to
    the small vocabulary the sandbox's unit-compatibility checks expect."""
    lowered = xbrl_unit.lower()
    if lowered == "usd":
        return "usd"
    if lowered in ("shares",):
        return "shares"
    if "per-shares" in lowered or "usd/shares" in lowered:
        return "usd_per_share"
    return lowered


def store_facts(engine: Engine, facts: list[dict]) -> int:
    """Insert facts, skipping any (accession_no, element_name, fiscal_year,
    unit) already present — re-running ingestion never duplicates."""
    if not facts:
        return 0
    with engine.begin() as conn:
        inserted = 0
        for fact in facts:
            result = conn.execute(
                text(
                    "INSERT INTO xbrl_facts "
                    "(fact_id, accession_no, cik, element_name, label, value, unit, "
                    "period_type, period_start, period_end, fiscal_year, fiscal_period, source_url) "
                    "VALUES (:fact_id, :accession_no, :cik, :element_name, :label, :value, :unit, "
                    ":period_type, :period_start, :period_end, :fiscal_year, :fiscal_period, :source_url) "
                    "ON CONFLICT (fact_id) DO NOTHING"
                ),
                fact,
            )
            inserted += result.rowcount
    return inserted
