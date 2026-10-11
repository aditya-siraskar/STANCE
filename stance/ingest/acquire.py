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

# Anchored to the repo root (two levels up from this file: stance/ingest/)
# rather than the notebook's cwd, so the cache lands in the same place
# whether a notebook runs from notebooks/ or the repo root.
RAW_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
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


def _scan_10k_block(block: dict, target_fiscal_years: list[int]) -> list[dict]:
    """Extracts matching 10-K entries from one filings block — either
    `submissions['filings']['recent']` or a paginated older-filings page,
    which share the same flat array-of-fields shape."""
    forms = block.get("form", [])
    accessions = block.get("accessionNumber", [])
    report_dates = block.get("reportDate", [])
    filing_dates = block.get("filingDate", [])
    primary_docs = block.get("primaryDocument", [])

    results = []
    for i, form in enumerate(forms):
        if form != "10-K":
            continue
        report_date = report_dates[i]
        if not report_date:  # a handful of old filings have an empty reportDate
            continue
        fiscal_year = int(report_date[:4])
        if fiscal_year not in target_fiscal_years:
            continue
        results.append(
            {
                "accession_no": accessions[i],
                "form_type": form,
                "fiscal_year": fiscal_year,
                "filing_date": filing_dates[i],
                "primary_doc": primary_docs[i],
            }
        )
    return results


def fetch_submissions_page(filename: str) -> dict:
    """Fetches one paginated page of a company's older filing history, as
    referenced by `submissions['filings']['files']`. Same flat shape as
    the 'recent' block, just not wrapped under 'filings'."""
    return _rate_limited_get(f"https://data.sec.gov/submissions/{filename}").json()


def find_10k_accessions(submissions: dict, target_fiscal_years: list[int]) -> list[dict]:
    """Filter a company's `submissions` JSON down to its 10-K filings whose
    report period falls in the target fiscal years. Uses reportDate (the
    filing's period-of-report) rather than filingDate, since a FY24 10-K is
    typically filed in FY25 — matching on filingDate would miss it.

    `filings.recent` only holds a company's most recent filings — not
    bounded by fiscal year, by filing count. A high filing-volume company
    (e.g. a bank filing hundreds of Form 4s a year) can push even a
    recent 10-K out of that window entirely. When a target year isn't
    found there, we additionally walk `filings.files` (older filings,
    paginated, newest page first) until every target year is found or the
    pages run out — so this only costs extra requests when actually needed.
    """
    recent = submissions.get("filings", {}).get("recent", {})
    results = _scan_10k_block(recent, target_fiscal_years)
    missing_years = set(target_fiscal_years) - {r["fiscal_year"] for r in results}

    for page in submissions.get("filings", {}).get("files", []):
        if not missing_years:
            break
        page_data = fetch_submissions_page(page["name"])
        for r in _scan_10k_block(page_data, target_fiscal_years):
            if r["fiscal_year"] in missing_years:
                results.append(r)
                missing_years.discard(r["fiscal_year"])

    return results


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
