"""Covers T8.1 (cited draft, placeholder substitution) from
AGENT_TEST_CASES.md."""
from decimal import Decimal

from stance.agents import writer


def test_format_fast_path_answer_includes_fact_id_citation():
    fact = {
        "fiscal_year": 2024, "value": Decimal("391035000000"), "unit": "usd",
        "accession_no": "0000320193-24-000123", "fact_id": "fact-abc123",
    }
    answer = writer.format_fast_path_answer("revenue", fact)
    assert "391,035,000,000" in answer
    assert "0000320193-24-000123" in answer
    assert "fact-abc123" in answer


def test_draft_narrative_answer_substitutes_placeholder_after_llm_call(monkeypatch):
    monkeypatch.setattr(writer, "complete", lambda node, messages: "Growth was {{spec-xyz}}.")
    sections = [{"accession_no": "acc-1", "item_code": "7", "text": "Revenue grew this year."}]
    result = writer.draft_narrative_answer("How much did revenue grow?", sections, {"spec-xyz": "10.55%"})
    assert result == "Growth was 10.55%."
    assert "{{" not in result  # placeholder must not survive into the final answer
