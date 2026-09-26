"""Writer — composes the final answer. Numeric fast-path answers are
formatted deterministically (no LLM: there is nothing to draft, only a
fact to cite). Narrative/full-path answers are drafted by an LLM given
ONLY the retrieved section text plus computed values as {{spec_id}}
placeholders — the model never sees the resolved decimal for a
computation, so it cannot type its own number into the prose even if the
retrieved text contains an injected one (see verifier.py for the second
line of defence).
"""
from __future__ import annotations

from decimal import Decimal

from stance.llm import complete

_SYSTEM_PROMPT = """You are a financial-filings writer. You are given retrieved \
filing excerpts, each labelled with a citation tag like [ACCESSION|ITEM]. Write \
a concise answer to the question using ONLY the given excerpts. Every factual \
claim must be followed by its citation tag, e.g. "...intense competition [0000320193-24-000123|1A]". \
If a computed value placeholder like {{spec-abc123}} is given, use it exactly \
as-is in your answer text — do not replace it with a number yourself, and do \
not state any number that isn't given to you verbatim in the excerpts or as a \
placeholder. If the excerpts do not answer the question, say so explicitly \
instead of guessing."""


def format_fast_path_answer(concept: str, fact: dict) -> str:
    """Deterministic formatting for a single resolved fact — no LLM
    involved, because there is no prose to draft."""
    value = Decimal(str(fact["value"]))
    formatted = f"{value:,.0f}" if fact["unit"] == "usd" else str(value)
    return (
        f"{concept.replace('_', ' ').title()} for FY{fact['fiscal_year']}: "
        f"{formatted} {fact['unit'].upper()} "
        f"[{fact['accession_no']}, fact_id={fact['fact_id']}]"
    )


def draft_narrative_answer(question: str, sections: list[dict], placeholders: dict[str, str]) -> str:
    """sections: expanded section dicts (accession_no, item_code, text).
    placeholders: {spec_id: 'formatted value + unit'} for any computed
    figures relevant to this answer, substituted into the draft AFTER the
    LLM call — the model only ever sees and echoes the {{spec_id}} token.
    """
    excerpt_block = "\n\n".join(
        f"[{s['accession_no']}|{s['item_code']}]\n{s['text'][:2000]}" for s in sections
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"Question: {question}\n\nExcerpts:\n{excerpt_block}"},
    ]
    draft = complete("writer", messages)

    for spec_id, formatted_value in placeholders.items():
        draft = draft.replace(f"{{{{{spec_id}}}}}", formatted_value)
    return draft
