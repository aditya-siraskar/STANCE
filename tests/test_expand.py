from unittest.mock import MagicMock

from stance.retrieval.expand import expand_to_sections


def test_expand_deduplicates_and_preserves_first_seen_order(monkeypatch):
    chunks = [
        {"section_id": "sec-A", "score": 0.9},
        {"section_id": "sec-B", "score": 0.8},
        {"section_id": "sec-A", "score": 0.7},  # duplicate section, lower rank
    ]

    fake_rows = [
        {"section_id": "sec-A", "accession_no": "acc-1", "item_code": "1A",
         "title": "Item 1A", "text": "risk text"},
        {"section_id": "sec-B", "accession_no": "acc-1", "item_code": "7",
         "title": "Item 7", "text": "mdna text"},
    ]

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value.execute.return_value.mappings.return_value.all.return_value = fake_rows
    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_conn

    sections = expand_to_sections(mock_engine, chunks)
    assert [s["section_id"] for s in sections] == ["sec-A", "sec-B"]


def test_expand_empty_input_returns_empty():
    assert expand_to_sections(MagicMock(), []) == []
