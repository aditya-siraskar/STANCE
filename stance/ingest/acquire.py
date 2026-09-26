"""Fetch filings from EDGAR by known accession number, rate-limited and cached.

At this project's scale (10 filings) we skip daily-index polling entirely —
accession numbers for the watchlist are looked up once via each company's
`submissions` JSON and pinned in `FILINGS`, so ingestion is deterministic
and reproducible across notebook sessions.
"""
from __future__ import annotations

import time
from pathlib import Path

import requests

from stance.config import settings

RAW_DIR = Path("/kaggle/working/raw")
_last_request_ts = 0.0


def _rate_limited_get(url: str) -> requests.Response:
    global _last_request_ts
    min_interval = 1.0 / settings.edgar_rate_limit_per_sec
    elapsed = time.monotonic() - _last_request_ts
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    resp = requests.get(url, headers={"User-Agent": settings.sec_user_agent}, timeout=30)
    _last_request_ts = time.monotonic()
    resp.raise_for_status()
    return resp


def fetch_submissions(cik: str) -> dict:
    """Company's filing history — used to find accession numbers for the
    watchlist's target fiscal years."""
    padded = cik.zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{padded}.json"
    return _rate_limited_get(url).json()


def fetch_company_facts(cik: str) -> dict:
    """Every XBRL fact the company has ever tagged, across all filings."""
    padded = cik.zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded}.json"
    return _rate_limited_get(url).json()


def fetch_filing_document(cik: str, accession_no: str, primary_doc: str) -> str:
    """Raw iXBRL HTML for one filing's primary document, cached to disk so a
    re-run doesn't re-hit EDGAR."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = RAW_DIR / f"{accession_no}.html"
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    accession_nodash = accession_no.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_nodash}/{primary_doc}"
    html = _rate_limited_get(url).text
    cache_path.write_text(html, encoding="utf-8")
    return html
