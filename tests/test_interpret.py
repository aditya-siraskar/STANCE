from decimal import Decimal

import pytest

from stance.contracts import FactNotFound
from stance.numeric import executor, interpret

FACTS = {
    ("revenue", "cik1", 2024): {"fact_id": "f-rev-24", "value": Decimal("391035000000"), "unit": "usd", "fiscal_year": 2024, "accession_no": "acc-24"},
    ("revenue", "cik1", 2023): {"fact_id": "f-rev-23", "value": Decimal("383285000000"), "unit": "usd", "fiscal_year": 2023, "accession_no": "acc-23"},
}
FACTS_BY_ID = {f["fact_id"]: f for f in FACTS.values()}


def _fake_resolve_fact(engine, concept, cik, fiscal_year, fiscal_period="FY"):
    key = (concept, cik, fiscal_year)
    if key not in FACTS:
        raise FactNotFound(f"no fact for {key}")
    return FACTS[key]


def _fake_fetch_fact_by_id(engine, fact_id):
    if fact_id not in FACTS_BY_ID:
        raise FactNotFound(f"fact_id '{fact_id}' not found")
    return FACTS_BY_ID[fact_id]


def test_detect_concept_defaults_to_revenue():
    assert interpret.detect_concept("What was the operating margin?") == "operating_income"
    assert interpret.detect_concept("What was net income?") == "net_income"
    assert interpret.detect_concept("How is the company doing?") == "revenue"


def test_detect_operation():
    assert interpret.detect_operation("revenue growth YoY") == "growth_rate"
    assert interpret.detect_operation("operating margin") == "margin"
    assert interpret.detect_operation("what was revenue") is None


def test_simple_lookup_single_year(monkeypatch):
    monkeypatch.setattr(interpret, "resolve_fact", _fake_resolve_fact)
    answer, fact_ids = interpret.answer_numeric_step(None, "What was FY24 revenue?", "cik1", [2024])
    assert fact_ids == ["f-rev-24"]
    assert "391,035,000,000" in answer


def test_growth_rate_across_two_years(monkeypatch):
    monkeypatch.setattr(interpret, "resolve_fact", _fake_resolve_fact)
    monkeypatch.setattr(executor, "fetch_fact_by_id", _fake_fetch_fact_by_id)
    answer, fact_ids = interpret.answer_numeric_step(
        None, "What was revenue growth?", "cik1", [2023, 2024]
    )
    assert set(fact_ids) == {"f-rev-24", "f-rev-23"}
    assert "2.02%" in answer


def test_missing_fact_propagates_loudly(monkeypatch):
    monkeypatch.setattr(interpret, "resolve_fact", _fake_resolve_fact)
    with pytest.raises(FactNotFound):
        interpret.answer_numeric_step(None, "What was FY21 revenue?", "cik1", [2021])
