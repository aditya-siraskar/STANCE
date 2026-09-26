"""Whitelisted operation registry. Facts are resolved to Decimal *outside*
this module and passed in — the sandbox never touches the database, the
network, or the filesystem, and every operation checks unit/period
compatibility before computing.
"""
from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal, InvalidOperation

from stance.contracts import UnitMismatchError

# unit -> compatible units for each op family (kept explicit rather than
# clever, so the compatibility rule is auditable by inspection)
_ADDITIVE_UNITS = {"usd", "usd_per_share"}


def _require_units_match(a_unit: str, b_unit: str) -> None:
    if a_unit != b_unit:
        raise UnitMismatchError(f"cannot combine units '{a_unit}' and '{b_unit}'")


def op_sum(values: list[Decimal], units: list[str]) -> Decimal:
    for u in units:
        if u not in _ADDITIVE_UNITS:
            raise UnitMismatchError(f"sum requires additive units, got '{u}'")
    for u in units[1:]:
        _require_units_match(units[0], u)
    return sum(values, Decimal(0))


def op_difference(a: Decimal, b: Decimal, a_unit: str, b_unit: str) -> Decimal:
    _require_units_match(a_unit, b_unit)
    return a - b


def op_ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        raise ZeroDivisionError("ratio denominator is zero")
    return numerator / denominator


def op_growth_rate(current: Decimal, prior: Decimal, current_unit: str, prior_unit: str) -> Decimal:
    _require_units_match(current_unit, prior_unit)
    if prior == 0:
        raise ZeroDivisionError("growth_rate: prior-period value is zero")
    return (current - prior) / abs(prior) * Decimal(100)


def op_margin(numerator: Decimal, denominator: Decimal, num_unit: str, den_unit: str) -> Decimal:
    _require_units_match(num_unit, den_unit)
    if denominator == 0:
        raise ZeroDivisionError("margin denominator is zero")
    return numerator / denominator * Decimal(100)


def op_cagr(ending: Decimal, beginning: Decimal, years: int, unit_a: str, unit_b: str) -> Decimal:
    _require_units_match(unit_a, unit_b)
    if beginning <= 0:
        raise UnitMismatchError("cagr requires a positive beginning value")
    if years <= 0:
        raise ValueError("cagr requires years > 0")
    ratio = ending / beginning
    return (ratio ** (Decimal(1) / Decimal(years)) - 1) * Decimal(100)


def op_per_share(value: Decimal, shares: Decimal, value_unit: str, shares_unit: str) -> Decimal:
    if shares_unit != "shares" or value_unit != "usd":
        raise UnitMismatchError(
            f"per_share requires usd/shares, got '{value_unit}'/'{shares_unit}'"
        )
    if shares == 0:
        raise ZeroDivisionError("per_share: shares outstanding is zero")
    return value / shares


def op_yoy_delta(current: Decimal, prior: Decimal, current_unit: str, prior_unit: str) -> Decimal:
    _require_units_match(current_unit, prior_unit)
    return current - prior


OPS: dict[str, Callable] = {
    "sum": op_sum,
    "difference": op_difference,
    "ratio": op_ratio,
    "growth_rate": op_growth_rate,
    "margin": op_margin,
    "cagr": op_cagr,
    "per_share": op_per_share,
    "yoy_delta": op_yoy_delta,
}


def execute(operation: str, *args, rounding: int = 2, **kwargs) -> Decimal:
    """Run a whitelisted operation and round the result. Raises
    UnitMismatchError / ZeroDivisionError / KeyError on invalid input —
    it never silently coerces or estimates."""
    if operation not in OPS:
        raise KeyError(f"unknown operation '{operation}' — not in the whitelist")
    try:
        result = OPS[operation](*args, **kwargs)
    except InvalidOperation as exc:
        raise UnitMismatchError(str(exc)) from exc
    quantum = Decimal(1).scaleb(-rounding)
    return result.quantize(quantum)
