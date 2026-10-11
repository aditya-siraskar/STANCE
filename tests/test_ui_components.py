import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "ui"))

from ui_components import kpi_row, kpi_tile  # noqa: E402


def test_kpi_tile_renders_label_and_value():
    html = kpi_tile("Figures checked", "6")
    assert "Figures checked" in html
    assert ">6<" in html
    assert "kpi-accent-mid" in html


def test_kpi_tile_accent_variant():
    html = kpi_tile("Rejected", "0", accent="dark")
    assert "kpi-accent-dark" in html


def test_kpi_row_renders_all_items_once():
    html = kpi_row([("A", "1"), ("B", "2"), ("C", "3")])
    assert html.count("kpi-tile") == 3
    assert "A" in html and "B" in html and "C" in html
