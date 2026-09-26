"""Item-boundary segmentation: Item 1A (Risk Factors), 7 (MD&A),
7A (Market risk), 8 (Financial statements and notes).

This is the step most RAG pipelines skip, and the one that most improves
retrieval quality — "what are their risks" must never retrieve from MD&A.
Boundaries are found with an ordered regex scan rather than a single
global regex, so the *last* occurrence of each item header (past the
table-of-contents references to it) is what actually gets used.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

SEGMENT_VERSION = "segment-v1"

ITEM_PATTERNS: dict[str, re.Pattern] = {
    "1A": re.compile(r"item\s+1a\.?\s+risk\s+factors", re.IGNORECASE),
    "7": re.compile(
        r"item\s+7\.?\s+management.?s\s+discussion\s+and\s+analysis", re.IGNORECASE
    ),
    "7A": re.compile(
        r"item\s+7a\.?\s+quantitative\s+and\s+qualitative\s+disclosures", re.IGNORECASE
    ),
    "8": re.compile(
        r"item\s+8\.?\s+financial\s+statements\s+and\s+supplementary\s+data",
        re.IGNORECASE,
    ),
}

# Order defines both the expected reading order and each section's end
# boundary (start of the next found item).
ITEM_ORDER = ["1A", "7", "7A", "8"]


@dataclass
class Section:
    item_code: str
    title: str
    text: str
    char_start: int
    char_end: int
    confidence: float  # 1.0 = single clean match, lower = heuristic fallback


def _last_match(pattern: re.Pattern, text: str) -> re.Match | None:
    """The true section header is typically the LAST match — earlier ones
    are almost always table-of-contents references."""
    matches = list(pattern.finditer(text))
    return matches[-1] if matches else None


def segment_filing(text: str) -> list[Section]:
    starts: dict[str, int] = {}
    for item_code in ITEM_ORDER:
        match = _last_match(ITEM_PATTERNS[item_code], text)
        if match:
            starts[item_code] = match.start()

    sections: list[Section] = []
    found_codes = [c for c in ITEM_ORDER if c in starts]
    for i, item_code in enumerate(found_codes):
        start = starts[item_code]
        end = starts[found_codes[i + 1]] if i + 1 < len(found_codes) else len(text)
        body = text[start:end].strip()
        confidence = 1.0 if body else 0.0
        sections.append(
            Section(
                item_code=item_code,
                title=f"Item {item_code}",
                text=body,
                char_start=start,
                char_end=end,
                confidence=confidence,
            )
        )
    return sections
