"""Covers T3.1 (fast path) and T3.2 (full path) from AGENT_TEST_CASES.md."""
from stance.agents.router import route
from stance.contracts import Plan, PlanStep, Scope

SINGLE_CO_ONE_YEAR = Scope(ciks=["0000320193"], tickers=["AAPL"], fiscal_years=[2024])
TWO_COMPANIES = Scope(ciks=["0000320193", "0000789019"], tickers=["AAPL", "MSFT"], fiscal_years=[2024])


def test_single_numeric_step_routes_fast():
    plan = Plan(
        question="What was Apple's FY24 revenue?",
        steps=[PlanStep(sub_question="AAPL FY24 revenue", kind="numeric", scope=SINGLE_CO_ONE_YEAR)],
    )
    assert route(plan) == "fast"


def test_narrative_step_never_routes_fast():
    plan = Plan(
        question="What are Apple's risks?",
        steps=[PlanStep(sub_question="AAPL risks", kind="narrative", scope=SINGLE_CO_ONE_YEAR)],
    )
    assert route(plan) == "full"


def test_multi_company_numeric_routes_full():
    plan = Plan(
        question="Compare Apple and Microsoft FY24 revenue",
        steps=[PlanStep(sub_question="compare revenue", kind="numeric", scope=TWO_COMPANIES)],
    )
    assert route(plan) == "full"


def test_multi_step_plan_routes_full():
    plan = Plan(
        question="Apple FY24 revenue and risks",
        steps=[
            PlanStep(sub_question="AAPL FY24 revenue", kind="numeric", scope=SINGLE_CO_ONE_YEAR),
            PlanStep(sub_question="AAPL risks", kind="narrative", scope=SINGLE_CO_ONE_YEAR),
        ],
    )
    assert route(plan) == "full"
