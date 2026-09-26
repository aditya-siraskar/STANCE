"""Sandbox tests — covers Phase 3 test cases T7.1 (unit-safe computation)
and T7.2 (incompatible units) from AGENT_TEST_CASES.md."""
from decimal import Decimal

import pytest

from stance.contracts import UnitMismatchError
from stance.numeric.sandbox import execute


def test_growth_rate_matches_hand_calculation():
    # T7.1: (110 - 100) / 100 * 100 = 10.00%
    result = execute("growth_rate", Decimal("110"), Decimal("100"), "usd", "usd")
    assert result == Decimal("10.00")


def test_margin_computation():
    result = execute("margin", Decimal("30"), Decimal("120"), "usd", "usd")
    assert result == Decimal("25.00")


def test_incompatible_units_rejected():
    # T7.2: USD duration fact vs. shares instant fact must not silently combine
    with pytest.raises(UnitMismatchError):
        execute("difference", Decimal("100"), Decimal("5"), "usd", "shares")


def test_per_share_requires_correct_units():
    with pytest.raises(UnitMismatchError):
        execute("per_share", Decimal("100"), Decimal("5"), "usd", "usd")


def test_zero_denominator_fails_loudly():
    with pytest.raises(ZeroDivisionError):
        execute("ratio", Decimal("10"), Decimal("0"))


def test_unknown_operation_rejected():
    with pytest.raises(KeyError):
        execute("multiply_by_two", Decimal("10"))
