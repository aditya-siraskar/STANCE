"""Intake & scope resolution — deterministic, no LLM. Ticker/company-name
matching against the watchlist and relative-period parsing both happen
here; an unresolvable entity returns AmbiguousScope rather than guessing,
because letting a model guess a CIK is a silent failure source.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine

from stance.contracts import Scope

_RELATIVE_YEARS_RE = re.compile(r"last\s+(one|two|three|four|five|\d+)\s+years?", re.IGNORECASE)
_FY_RE = re.compile(r"\bFY\s?(\d{2,4})\b", re.IGNORECASE)
_WORD_TO_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


@dataclass
class AmbiguousScope:
    """Returned instead of a Scope when the entity or period cannot be
    resolved unambiguously. The caller (graph.py) surfaces this as a
    clarifying question rather than guessing."""

    reason: str
    candidates: list[str]


def _load_companies(engine: Engine) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT cik, ticker, name FROM companies")).mappings().all()
    return [dict(r) for r in rows]


def _match_companies(question: str, companies: list[dict]) -> list[dict]:
    q = question.lower()
    matches = []
    for c in companies:
        if re.search(rf"\b{re.escape(c['ticker'].lower())}\b", q):
            matches.append(c)
            continue
        # match on the first word of the company name (e.g. "Apple", "Microsoft")
        first_word = c["name"].split()[0].lower()
        if len(first_word) > 3 and re.search(rf"\b{re.escape(first_word)}\b", q):
            matches.append(c)
    return matches


def _resolve_fiscal_years(question: str, latest_available_year: int) -> list[int]:
    fy_matches = _FY_RE.findall(question)
    if fy_matches:
        years = []
        for y in fy_matches:
            year = int(y)
            year = 2000 + year if year < 100 else year
            years.append(year)
        return sorted(set(years))

    rel_match = _RELATIVE_YEARS_RE.search(question)
    if rel_match:
        token = rel_match.group(1).lower()
        n = _WORD_TO_NUM.get(token, int(token) if token.isdigit() else 1)
        return list(range(latest_available_year - n + 1, latest_available_year + 1))

    if re.search(r"\blast\s+year\b", question, re.IGNORECASE):
        return [latest_available_year]

    # Default: most recent fiscal year in the corpus.
    return [latest_available_year]


def resolve_scope(
    engine: Engine, question: str, latest_available_year: int = 2024
) -> Scope | AmbiguousScope:
    companies = _load_companies(engine)
    matched = _match_companies(question, companies)

    if not matched:
        return AmbiguousScope(
            reason="no company in the watchlist matched the question",
            candidates=[c["ticker"] for c in companies],
        )

    fiscal_years = _resolve_fiscal_years(question, latest_available_year)
    item_codes = ["1A"] if re.search(r"\brisk", question, re.IGNORECASE) else None

    return Scope(
        ciks=[c["cik"] for c in matched],
        tickers=[c["ticker"] for c in matched],
        fiscal_years=fiscal_years,
        item_codes=item_codes,
    )
