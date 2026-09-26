"""Parent-child chunking: small children (~400-600 tokens) for retrieval
precision, returning the enclosing section as the parent for generation
context. A [TABLE] block is never split across a chunk boundary.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import uuid4

CHUNKER_VERSION = "chunk-v1"

_TARGET_TOKENS = 500
_OVERLAP_TOKENS = 75
_CHARS_PER_TOKEN = 4  # rough estimate, good enough for chunk sizing


@dataclass
class Chunk:
    chunk_id: str
    text: str
    token_count: int


def _split_preserving_tables(text: str) -> list[str]:
    """Split on paragraph breaks, but keep each [TABLE]...[/TABLE] block
    as one atomic unit so it never gets split across chunks."""
    table_pattern = re.compile(r"\[TABLE\].*?\[/TABLE\]", re.DOTALL)
    units: list[str] = []
    last_end = 0
    for match in table_pattern.finditer(text):
        before = text[last_end : match.start()].strip()
        if before:
            units.extend(p for p in re.split(r"\n\s*\n", before) if p.strip())
        units.append(match.group(0))
        last_end = match.end()
    tail = text[last_end:].strip()
    if tail:
        units.extend(p for p in re.split(r"\n\s*\n", tail) if p.strip())
    return units


def chunk_section(section_text: str, target_tokens: int = _TARGET_TOKENS) -> list[Chunk]:
    units = _split_preserving_tables(section_text)
    target_chars = target_tokens * _CHARS_PER_TOKEN
    overlap_chars = _OVERLAP_TOKENS * _CHARS_PER_TOKEN

    chunks: list[Chunk] = []
    buffer = ""
    for unit in units:
        # A table block always starts its own chunk if the buffer already
        # has content, so it is never truncated by the size cap below.
        if unit.startswith("[TABLE]") and buffer:
            chunks.append(_make_chunk(buffer))
            buffer = ""

        candidate = f"{buffer}\n\n{unit}".strip() if buffer else unit
        if len(candidate) > target_chars and buffer:
            chunks.append(_make_chunk(buffer))
            carry = buffer[-overlap_chars:] if not buffer.startswith("[TABLE]") else ""
            buffer = f"{carry}\n\n{unit}".strip() if carry else unit
        else:
            buffer = candidate

    if buffer.strip():
        chunks.append(_make_chunk(buffer))
    return chunks


def _make_chunk(text: str) -> Chunk:
    return Chunk(
        chunk_id=f"chunk-{uuid4().hex[:12]}",
        text=text.strip(),
        token_count=len(text) // _CHARS_PER_TOKEN,
    )
