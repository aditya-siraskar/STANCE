"""Covers T2.1 (mixed decomposition) from AGENT_TEST_CASES.md, with the LLM
call mocked — the planner's job under test is parsing/validation, not the
model's own reasoning quality (that's an eval-harness concern, Phase 5)."""
import json

import pytest

from stance.agents import planner
from stance.contracts import Scope

SCOPE = Scope(ciks=["0000320193", "0000789019"], tickers=["AAPL", "MSFT"], fiscal_years=[2024])


def test_build_plan_parses_mixed_steps(monkeypatch):
    fake_response = json.dumps([
        {"sub_question": "What was AAPL FY24 revenue?", "kind": "numeric"},
        {"sub_question": "What was MSFT FY24 revenue?", "kind": "numeric"},
        {"sub_question": "What are AAPL's top risk factors?", "kind": "narrative"},
        {"sub_question": "What are MSFT's top risk factors?", "kind": "narrative"},
    ])
    monkeypatch.setattr(planner, "complete", lambda node, messages: fake_response)

    plan = planner.build_plan("Compare Apple and Microsoft FY24 revenue and risks", SCOPE)
    assert len(plan.steps) == 4
    assert sum(1 for s in plan.steps if s.kind == "numeric") == 2
    assert sum(1 for s in plan.steps if s.kind == "narrative") == 2
    assert all(s.scope == SCOPE for s in plan.steps)


def test_build_plan_strips_markdown_fence(monkeypatch):
    fenced = "```json\n" + json.dumps([{"sub_question": "q", "kind": "numeric"}]) + "\n```"
    monkeypatch.setattr(planner, "complete", lambda node, messages: fenced)
    plan = planner.build_plan("q", SCOPE)
    assert len(plan.steps) == 1


def test_build_plan_rejects_malformed_step(monkeypatch):
    monkeypatch.setattr(
        planner, "complete", lambda node, messages: json.dumps([{"sub_question": "q"}])
    )
    with pytest.raises(ValueError):
        planner.build_plan("q", SCOPE)


def test_build_plan_rejects_non_json(monkeypatch):
    monkeypatch.setattr(planner, "complete", lambda node, messages: "not json at all")
    with pytest.raises(ValueError):
        planner.build_plan("q", SCOPE)
