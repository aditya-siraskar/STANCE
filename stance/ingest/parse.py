"""Inline-XBRL HTML -> clean text. Strips iXBRL tagging noise and page
furniture, but preserves tables as structured markdown blocks rather than
flattening them into prose — a table flattened into prose is where a lot
of RAG pipelines quietly lose the numbers that matter.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

PARSER_VERSION = "parse-v1"

_STRIP_TAGS = ["script", "style", "ix:header", "xbrli:xbrl"]


def _table_to_markdown(table_tag) -> str:
    rows = []
    for tr in table_tag.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if any(cells):
            rows.append(cells)
    if not rows:
        return ""
    lines = ["[TABLE]"]
    for row in rows:
        lines.append(" | ".join(row))
    lines.append("[/TABLE]")
    return "\n".join(lines)


def parse_filing_html(html: str) -> str:
    """Returns clean text with tables preserved as [TABLE]...[/TABLE]
    markdown blocks in place, in document order."""
    soup = BeautifulSoup(html, "lxml")

    for tag_name in _STRIP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Replace each table with a placeholder text node so document order is
    # preserved when we walk get_text() afterwards.
    for table in soup.find_all("table"):
        md = _table_to_markdown(table)
        table.replace_with(md)

    text = soup.get_text("\n")
    # Collapse runs of blank lines/whitespace left by stripped markup.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
