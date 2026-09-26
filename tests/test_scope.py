"""Covers T1.1 (relative period resolution) and T1.2-equivalent (refuses to
guess an unmatched entity) from AGENT_TEST_CASES.md. Note: this project's
watchlist is fixed at 5 companies, so the "ambiguous ticker" case is
represented as "no watchlist company matched" rather than a genuine
cross-company EDGAR name collision — see README for that scoping note.
"""
from unittest.mock import MagicMock

from stance.agents.scope import AmbiguousScope, resolve_scope
from stance.contracts import Scope

FAKE_COMPANIES = [
    {"cik": "0000320193", "ticker": "AAPL", "name": "Apple Inc."},
    {"cik": "0000789019", "ticker": "MSFT", "name": "Microsoft Corporation"},
]


def _mock_engine():
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value.execute.return_value.mappings.return_value.all.return_value = (
        FAKE_COMPANIES
    )
    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_conn
    return mock_engine


def test_relative_period_resolution():
    scope = resolve_scope(_mock_engine(), "Apple's revenue over the last three years", 2024)
    assert isinstance(scope, Scope)
    assert scope.ciks == ["0000320193"]
    assert scope.fiscal_years == [2022, 2023, 2024]


def test_unmatched_entity_returns_ambiguous_not_a_guess():
    result = resolve_scope(_mock_engine(), "What were Delta's risk factors?", 2024)
    assert isinstance(result, AmbiguousScope)
    assert "AAPL" in result.candidates


def test_explicit_fy_and_risk_item_scoping():
    scope = resolve_scope(_mock_engine(), "What are Apple's FY2024 risk factors?", 2024)
    assert isinstance(scope, Scope)
    assert scope.fiscal_years == [2024]
    assert scope.item_codes == ["1A"]


def test_multi_company_match():
    scope = resolve_scope(_mock_engine(), "Compare Apple and Microsoft FY24 revenue", 2024)
    assert isinstance(scope, Scope)
    assert set(scope.tickers) == {"AAPL", "MSFT"}
