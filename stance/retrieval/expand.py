"""Child -> parent expansion: after retrieval+rerank narrows to the top
child chunks, expand each to its enclosing section for generation context,
deduplicating so the writer never sees the same section text twice.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def expand_to_sections(engine: Engine, chunks: list[dict]) -> list[dict]:
    """Given retrieved chunk rows (each with a section_id), return the
    distinct enclosing sections, in the order their best-ranked chunk
    first appeared."""
    seen: set[str] = set()
    ordered_section_ids: list[str] = []
    for chunk in chunks:
        section_id = chunk["section_id"]
        if section_id not in seen:
            seen.add(section_id)
            ordered_section_ids.append(section_id)

    if not ordered_section_ids:
        return []

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT section_id, accession_no, item_code, title, text "
                "FROM sections WHERE section_id = ANY(:ids)"
            ),
            {"ids": ordered_section_ids},
        ).mappings().all()

    by_id = {r["section_id"]: dict(r) for r in rows}
    return [by_id[sid] for sid in ordered_section_ids if sid in by_id]
