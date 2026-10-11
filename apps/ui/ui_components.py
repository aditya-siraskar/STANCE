"""Reusable glass-card HTML components for the UI — kept out of app.py (a
Streamlit script that can't itself be imported outside a Streamlit runtime)
so the markup is unit-testable, same rationale as pipeline_viz.py.
"""
from __future__ import annotations


def kpi_tile(label: str, value: str, accent: str = "mid") -> str:
    """One compact glass KPI tile: small uppercase label, large tabular-num
    value, a coloured left accent bar. `accent` is 'mid' or 'dark',
    matching the --blue-mid / --blue-dark theme tokens."""
    return (
        f'<div class="kpi-tile kpi-accent-{accent}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'</div>'
    )


def kpi_row(items: list[tuple[str, str]], accent: str = "mid") -> str:
    """A row of KPI tiles in a responsive grid."""
    tiles = "".join(kpi_tile(label, value, accent) for label, value in items)
    return f'<div class="kpi-row">{tiles}</div>'
