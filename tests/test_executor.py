"""Executor tests using a monkeypatched fact lookup — no live DB needed.
Covers T6.1 (growth rate spec executes correctly) and T6.2 (missing
operand fails loudly) from AGENT_TEST_CASES.md.
"""
from decimal import Decimal

import pytest

from stance.contracts import ComputationSpec, FactNotFound, Operand
from stance.numeric import executor

FAKE_FACTS = {
    "f-aapl-rev-2024": {"value": Decimal("391035000000"), "unit": "usd"},
    "f-aapl-rev-2023": {"value": Decimal("383285000000"), "unit": "usd"},
}


def _fake_fetch(engine, fact_id):
    if fact_id not in FAKE_FACTS:
        raise FactNotFound(f"fact_id '{fact_id}' does not exist in xbrl_facts")
    return FAKE_FACTS[fact_id]


def test_growth_rate_spec_executes(monkeypatch):
    monkeypatch.setattr(executor, "fetch_fact_by_id", _fake_fetch)
    spec = ComputationSpec(
        operation="growth_rate",
        operands=[
            Operand(role="current", fact_id="f-aapl-rev-2024"),
            Operand(role="prior", fact_id="f-aapl-rev-2023"),
        ],
        output_unit="percent",
    )
    result = executor.execute_spec(engine=None, spec=spec)
    assert result == Decimal("2.02")  # (391035-383285)/383285 * 100, rounded


def test_missing_fact_fails_loudly(monkeypatch):
    monkeypatch.setattr(executor, "fetch_fact_by_id", _fake_fetch)
    spec = ComputationSpec(
        operation="growth_rate",
        operands=[
            Operand(role="current", fact_id="f-aapl-rev-2024"),
            Operand(role="prior", fact_id="f-aapl-rev-2021-MISSING"),
        ],
        output_unit="percent",
    )
    with pytest.raises(FactNotFound):
        executor.execute_spec(engine=None, spec=spec)
