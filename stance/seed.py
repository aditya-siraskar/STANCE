"""Seed data: the watchlist and the deterministic concept->XBRL-tag aliases.

Kept as data, not hardcoded inside agent logic, so extending the watchlist
or fixing a tagging-convention mismatch never touches agent code.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

# 5 companies, 5 sectors — enough to make cross-company comparison non-trivial
# without the corpus size threatening the free-tier footprint.
WATCHLIST = [
    {"cik": "0000320193", "ticker": "AAPL", "name": "Apple Inc.", "sic": "3571"},
    {"cik": "0000789019", "ticker": "MSFT", "name": "Microsoft Corporation", "sic": "7372"},
    {"cik": "0000019617", "ticker": "JPM", "name": "JPMorgan Chase & Co.", "sic": "6021"},
    {"cik": "0000034088", "ticker": "XOM", "name": "Exxon Mobil Corporation", "sic": "2911"},
    {"cik": "0000078003", "ticker": "PFE", "name": "Pfizer Inc.", "sic": "2836"},
]

FISCAL_YEARS = [2023, 2024]

# Priority-ordered: resolver tries these in order per concept until one
# resolves for the given (cik, fiscal_year). No LLM anywhere in this path.
FACT_ALIASES = [
    # revenue
    ("revenue", "RevenueFromContractWithCustomerExcludingAssessedTax", None, 0),
    ("revenue", "Revenues", None, 1),
    ("revenue", "SalesRevenueNet", None, 2),
    ("revenue", "InterestAndDividendIncomeOperating", None, 3),  # bank-style filers
    # net income
    ("net_income", "NetIncomeLoss", None, 0),
    ("net_income", "ProfitLoss", None, 1),
    # total assets
    ("total_assets", "Assets", None, 0),
    # operating income (for margin computations)
    ("operating_income", "OperatingIncomeLoss", None, 0),
    # diluted EPS
    ("eps_diluted", "EarningsPerShareDiluted", None, 0),
]


def seed_companies(engine: Engine) -> None:
    with engine.begin() as conn:
        for c in WATCHLIST:
            conn.execute(
                text(
                    "INSERT INTO companies (cik, ticker, name, sic) "
                    "VALUES (:cik, :ticker, :name, :sic) "
                    "ON CONFLICT (cik) DO NOTHING"
                ),
                c,
            )


def seed_fact_aliases(engine: Engine) -> None:
    with engine.begin() as conn:
        for concept, element_name, cik, priority in FACT_ALIASES:
            conn.execute(
                text(
                    "INSERT INTO fact_aliases (concept, element_name, cik, priority) "
                    "VALUES (:concept, :element_name, :cik, :priority) "
                    "ON CONFLICT (concept, element_name, cik) DO NOTHING"
                ),
                {"concept": concept, "element_name": element_name, "cik": cik, "priority": priority},
            )


def seed_all(engine: Engine) -> None:
    seed_companies(engine)
    seed_fact_aliases(engine)
