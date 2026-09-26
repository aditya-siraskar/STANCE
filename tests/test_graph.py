"""End-to-end graph wiring test with every agent boundary mocked — proves
the graph topology and state threading are correct without needing a live
DB or LLM API key. Covers the clarify-branch (T1.2-style refusal to guess)
and a full numeric-only traversal producing a verified final answer.
"""
from stance.agents import graph as graph_module
from stance.agents.scope import AmbiguousScope
from stance.contracts import Plan, PlanStep, Scope, VerifierReport

SCOPE = Scope(ciks=["cik1"], tickers=["AAPL"], fiscal_years=[2024])


def _invoke(g, question):
    return g.invoke({"question": question}, config={"configurable": {"thread_id": "t1"}})


def test_ambiguous_scope_ends_at_clarification(monkeypatch):
    monkeypatch.setattr(graph_module, "resolve_scope", lambda engine, q, y: AmbiguousScope(
        reason="no match", candidates=["AAPL", "MSFT"]
    ))
    g = graph_module.build_graph(engine=None)
    result = _invoke(g, "What were Delta's risks?")
    assert "clarification" in result
    assert "AAPL" in result["clarification"]
    assert "final_answer" not in result  # must not proceed to answer on a guess


def test_full_numeric_traversal_produces_verified_answer(monkeypatch):
    plan = Plan(
        question="What was AAPL FY24 revenue?",
        steps=[PlanStep(sub_question="AAPL FY24 revenue", kind="numeric", scope=SCOPE)],
    )
    monkeypatch.setattr(graph_module, "resolve_scope", lambda engine, q, y: SCOPE)
    monkeypatch.setattr(graph_module, "build_plan", lambda q, s: plan)
    monkeypatch.setattr(graph_module, "route", lambda p: "fast")
    monkeypatch.setattr(
        graph_module, "answer_numeric_step",
        lambda engine, sub_q, cik, years: ("Revenue FY24: 391,035,000,000 USD [fact_id=f-1]", ["f-1"]),
    )
    monkeypatch.setattr(
        graph_module, "verify_draft",
        lambda engine, draft: VerifierReport(
            figures_checked=1, figures_traced=1, figures_rejected=0, citation_coverage=1.0
        ),
    )

    g = graph_module.build_graph(engine=None)
    result = _invoke(g, "What was AAPL FY24 revenue?")

    assert result["route"] == "fast"
    assert "391,035,000,000" in result["final_answer"]
    assert result["verifier_report"]["figures_rejected"] == 0
