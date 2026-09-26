from stance.ingest.chunk import chunk_section
from stance.ingest.parse import parse_filing_html
from stance.ingest.segment import segment_filing

SAMPLE_HTML = """
<html><body>
<p>Table of Contents references Item 1A. Risk Factors on page 5.</p>
<h2>Item 1A. Risk Factors</h2>
<p>We face intense competition in our markets.</p>
<h2>Item 7. Management's Discussion and Analysis</h2>
<p>Revenue increased year over year.</p>
<table><tr><td>Year</td><td>Revenue</td></tr><tr><td>2024</td><td>100</td></tr></table>
<h2>Item 8. Financial Statements and Supplementary Data</h2>
<p>See accompanying notes.</p>
</body></html>
"""


def test_parse_preserves_tables_and_strips_html():
    text = parse_filing_html(SAMPLE_HTML)
    assert "[TABLE]" in text
    assert "Year | Revenue" in text
    assert "<table>" not in text


def test_segment_finds_item_boundaries_and_skips_toc_reference():
    text = parse_filing_html(SAMPLE_HTML)
    sections = segment_filing(text)
    codes = [s.item_code for s in sections]
    assert codes == ["1A", "7", "8"]

    risk_section = next(s for s in sections if s.item_code == "1A")
    assert "intense competition" in risk_section.text
    # MD&A content must not leak into the risk-factors section
    assert "Revenue increased" not in risk_section.text


def test_chunk_never_splits_a_table():
    text = "Intro paragraph.\n\n[TABLE]\nYear | Revenue\n2024 | 100\n[/TABLE]\n\nClosing paragraph."
    chunks = chunk_section(text, target_tokens=5)  # force small chunks
    table_chunks = [c for c in chunks if "[TABLE]" in c.text]
    assert len(table_chunks) == 1
    assert "[/TABLE]" in table_chunks[0].text
