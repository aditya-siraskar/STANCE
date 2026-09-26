from stance.ingest.acquire import find_10k_accessions
from stance.ingest.facts import extract_facts, normalise_unit

FAKE_SUBMISSIONS = {
    "filings": {
        "recent": {
            "form": ["10-K", "10-Q", "10-K", "8-K"],
            "accessionNumber": ["0000320193-24-000123", "0000320193-24-000050",
                                 "0000320193-23-000106", "0000320193-24-000200"],
            "reportDate": ["2024-09-28", "2024-06-29", "2023-09-30", "2024-01-01"],
            "filingDate": ["2024-11-01", "2024-08-01", "2023-11-03", "2024-01-02"],
            "primaryDocument": ["aapl-20240928.htm", "aapl-20240629.htm",
                                 "aapl-20230930.htm", "aapl-20240101.htm"],
        }
    }
}

FAKE_COMPANY_FACTS = {
    "facts": {
        "us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "label": "Revenues",
                "units": {
                    "USD": [
                        {"end": "2024-09-28", "start": "2023-10-01", "val": 391035000000,
                         "accn": "0000320193-24-000123", "fy": 2024, "fp": "FY", "form": "10-K"},
                        {"end": "2023-09-30", "start": "2022-10-01", "val": 383285000000,
                         "accn": "0000320193-23-000106", "fy": 2023, "fp": "FY", "form": "10-K"},
                        # a 10-Q entry for the same element must be excluded
                        {"end": "2024-06-29", "start": "2024-04-01", "val": 90000000000,
                         "accn": "0000320193-24-000050", "fy": 2024, "fp": "Q3", "form": "10-Q"},
                    ]
                },
            },
            "Assets": {
                "label": "Total assets",
                "units": {
                    "USD": [
                        {"end": "2024-09-28", "val": 364980000000,
                         "accn": "0000320193-24-000123", "fy": 2024, "fp": "FY", "form": "10-K"},
                    ]
                },
            },
        }
    }
}


def test_find_10k_accessions_filters_form_and_year():
    results = find_10k_accessions(FAKE_SUBMISSIONS, target_fiscal_years=[2024])
    assert len(results) == 1
    assert results[0]["accession_no"] == "0000320193-24-000123"
    assert results[0]["form_type"] == "10-K"


def test_extract_facts_excludes_non_10k_and_wrong_period():
    facts = extract_facts(
        FAKE_COMPANY_FACTS,
        cik="0000320193",
        element_names=["RevenueFromContractWithCustomerExcludingAssessedTax", "Assets"],
        target_fiscal_years=[2023, 2024],
    )
    assert len(facts) == 3  # 2 revenue years + 1 assets year; the 10-Q entry excluded
    fy2024_revenue = next(
        f for f in facts
        if f["element_name"] == "RevenueFromContractWithCustomerExcludingAssessedTax"
        and f["fiscal_year"] == 2024
    )
    assert fy2024_revenue["value"] == 391035000000
    assert fy2024_revenue["period_type"] == "duration"
    assert fy2024_revenue["accession_no"] == "0000320193-24-000123"


def test_extract_facts_is_deterministic_across_calls():
    """Re-running extraction on the same input must yield the same fact_id
    — this is what makes ingestion idempotent."""
    first = extract_facts(
        FAKE_COMPANY_FACTS, "0000320193",
        ["RevenueFromContractWithCustomerExcludingAssessedTax"], [2024],
    )
    second = extract_facts(
        FAKE_COMPANY_FACTS, "0000320193",
        ["RevenueFromContractWithCustomerExcludingAssessedTax"], [2024],
    )
    assert first[0]["fact_id"] == second[0]["fact_id"]


def test_normalise_unit():
    assert normalise_unit("USD") == "usd"
    assert normalise_unit("shares") == "shares"
    assert normalise_unit("USD-per-shares") == "usd_per_share"
