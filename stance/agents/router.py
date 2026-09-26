"""Router — triages a resolved Plan to the cheap fast-path (single numeric
fact, single company/period, no retrieval needed) or the full path
(narrative or multi-company/multi-period).

Design simplification vs. the original architecture: since the planner has
already typed every step 'narrative'/'numeric' via its own LLM call, this
router applies a deterministic rule over that typed structure instead of
spending a second model call on triage — same behaviour, one fewer LLM
round trip, and the routing decision is trivially auditable.
"""
from __future__ import annotations

from stance.contracts import Plan


def route(plan: Plan) -> str:
    """Returns 'fast' only for a single numeric step scoped to exactly one
    company and one fiscal period — anything narrative, multi-company, or
    multi-period goes through full retrieval. A misroute toward 'fast' for
    narrative content would mean answering from model priors instead of
    the filings, so this rule is deliberately conservative."""
    if len(plan.steps) != 1:
        return "full"

    step = plan.steps[0]
    if step.kind != "numeric":
        return "full"

    if len(step.scope.ciks) != 1 or len(step.scope.fiscal_years) != 1:
        return "full"

    return "fast"
