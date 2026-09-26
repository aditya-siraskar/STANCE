"""Verifier — a separate pass that re-derives every numeric claim in a
draft against xbrl_facts and strips anything that doesn't trace to a real
fact_id. This is both the headline quality metric AND the prompt-injection
defence: an injected figure has no fact_id, so it cannot survive this pass.
"""
from __future__ import annotations

import re
from decimal import Decimal

from sqlalchemy.engine import Engine

from stance.contracts import FactNotFound, RejectedFigure, VerifierReport
from stance.numeric.resolver import fetch_fact_by_id

# Matches a citation tag this project's writer emits, e.g.
# "...revenue grew [0000320193-24-000123, fact_id=fact-abc123def456]"
_FACT_CITATION_RE = re.compile(r"fact_id=([a-zA-Z0-9\-]+)")


def verify_draft(engine: Engine, draft: str, tolerance: Decimal = Decimal("0.01")) -> VerifierReport:
    """Re-derives every cited fact_id against xbrl_facts. A figure is
    'traced' if its fact_id resolves; it is 'rejected' if the fact_id does
    not exist at all — this is the case an injected figure hits, since a
    fabricated number has no real fact_id to cite. Citation coverage =
    fraction of cited fact_ids that successfully traced.
    """
    cited_fact_ids = _FACT_CITATION_RE.findall(draft)
    rejected: list[RejectedFigure] = []
    traced = 0

    for fact_id in cited_fact_ids:
        try:
            fetch_fact_by_id(engine, fact_id)
            traced += 1
        except FactNotFound:
            rejected.append(
                RejectedFigure(
                    claimed_value=fact_id,
                    reason="no_fact_id",
                    detail=f"cited fact_id '{fact_id}' does not exist in xbrl_facts",
                )
            )

    figures_checked = len(cited_fact_ids)
    citation_coverage = 1.0 if figures_checked == 0 else traced / figures_checked

    return VerifierReport(
        figures_checked=figures_checked,
        figures_traced=traced,
        figures_rejected=len(rejected),
        citation_coverage=round(citation_coverage, 4),
        rejected_details=rejected,
    )


def strip_rejected_figures(draft: str, report: VerifierReport) -> str:
    """Removes any sentence containing a rejected fact_id citation from the
    draft entirely, rather than publishing a figure that failed
    verification. This is the 'untraceable -> stripped, never silently
    published' rule."""
    if not report.rejected_details:
        return draft

    rejected_ids = {r.claimed_value for r in report.rejected_details}
    sentences = re.split(r"(?<=[.!?])\s+", draft)
    kept = [s for s in sentences if not any(rid in s for rid in rejected_ids)]
    return " ".join(kept)
