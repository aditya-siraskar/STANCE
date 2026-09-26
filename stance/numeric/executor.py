"""Ties a ComputationSpec to the sandbox: resolves every operand's fact_id
(or recursively executes a nested spec_id) to a Decimal+unit *outside* the
sandbox, then calls the whitelisted operation. This is the only place
ComputationSpec, resolver, and sandbox meet.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.engine import Engine

from stance.contracts import ComputationSpec, FactNotFound
from stance.numeric import sandbox
from stance.numeric.resolver import fetch_fact_by_id

# ordered positional argument names each op expects, after the leading values
_OP_ARG_ORDER: dict[str, list[str]] = {
    "growth_rate": ["current", "prior"],
    "margin": ["numerator", "denominator"],
    "yoy_delta": ["current", "prior"],
    "difference": ["a", "b"],  # generic roles; alias to a/b below
    "ratio": ["numerator", "denominator"],
    "per_share": ["value", "shares"],
    "cagr": ["ending", "beginning"],
}


def execute_spec(
    engine: Engine, spec: ComputationSpec, specs_by_id: dict[str, ComputationSpec] | None = None
) -> Decimal:
    """Resolve every operand and run the operation. Raises FactNotFound if
    any referenced fact_id is missing — never estimates, never falls back
    to a plausible-looking value."""
    specs_by_id = specs_by_id or {}
    resolved: dict[str, tuple[Decimal, str]] = {}

    for operand in spec.operands:
        if operand.fact_id:
            fact = fetch_fact_by_id(engine, operand.fact_id)
            resolved[operand.role] = (Decimal(str(fact["value"])), fact["unit"])
        elif operand.spec_id:
            nested_spec = specs_by_id.get(operand.spec_id)
            if nested_spec is None:
                raise FactNotFound(f"nested spec_id '{operand.spec_id}' not provided")
            nested_value = execute_spec(engine, nested_spec, specs_by_id)
            resolved[operand.role] = (nested_value, nested_spec.output_unit)
        else:
            raise ValueError(f"operand '{operand.role}' has neither fact_id nor spec_id")

    if spec.operation == "sum":
        values = [v for v, _ in resolved.values()]
        units = [u for _, u in resolved.values()]
        return sandbox.execute("sum", values, units, rounding=spec.rounding)

    # Operand roles ARE the sandbox function's parameter names
    # (current/prior, numerator/denominator, ...) — use them directly.
    arg_names = _OP_ARG_ORDER[spec.operation]
    missing = [r for r in arg_names if r not in resolved]
    if missing:
        raise ValueError(f"'{spec.operation}' spec missing operand role(s): {missing}")
    values = [resolved[r][0] for r in arg_names]
    units = [resolved[r][1] for r in arg_names]

    if spec.operation == "cagr":
        # cagr also needs `years` — derive from operand metadata is out of
        # scope for this simple executor; expect callers to pass a 2-point
        # growth_rate/yoy_delta instead unless years is embedded elsewhere.
        raise NotImplementedError("cagr execution requires a 'years' operand — not wired yet")

    return sandbox.execute(spec.operation, values[0], values[1], units[0], units[1], rounding=spec.rounding)
