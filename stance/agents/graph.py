"""LangGraph assembly: scope -> planner -> router -> answer_steps -> verify.

Numeric steps are always answered deterministically (resolver/calculator/
sandbox), in both the fast and full route — the LLM is only ever invoked
for the planner (decomposition) and the writer (drafting narrative prose
from retrieved text). `route` is computed and recorded for the
cost-per-query metric even though, structurally, a plan with no narrative
steps never invokes retrieval regardless of the label.

Requires the `agents` extra (`pip install -e ".[agents]"`).
"""
from __future__ import annotations

from typing import TypedDict

from sqlalchemy.engine import Engine

from stance.agents.planner import build_plan
from stance.agents.router import route
from stance.agents.scope import AmbiguousScope, resolve_scope
from stance.agents.verifier import strip_rejected_figures, verify_draft
from stance.agents.writer import draft_narrative_answer
from stance.contracts import FactNotFound, Scope
from stance.numeric.interpret import answer_numeric_step
from stance.retrieval.expand import expand_to_sections
from stance.retrieval.hybrid import hybrid_search
from stance.retrieval.rerank import rerank


class GraphState(TypedDict, total=False):
    question: str
    scope: Scope
    clarification: str
    plan_steps: list[dict]
    route: str
    step_answers: list[str]
    fact_ids_used: list[str]
    draft: str
    verifier_report: dict
    final_answer: str


def build_graph(engine: Engine, latest_available_year: int = 2024):
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, StateGraph

    def scope_node(state: GraphState) -> GraphState:
        result = resolve_scope(engine, state["question"], latest_available_year)
        if isinstance(result, AmbiguousScope):
            return {"clarification": f"Could not resolve the question: {result.reason}. "
                                       f"Known tickers: {', '.join(result.candidates)}"}
        return {"scope": result}

    def scope_branch(state: GraphState) -> str:
        return "clarify" if "clarification" in state else "planner"

    def planner_node(state: GraphState) -> GraphState:
        plan = build_plan(state["question"], state["scope"])
        return {"plan_steps": [s.model_dump() for s in plan.steps], "route": route(plan)}

    def answer_steps_node(state: GraphState) -> GraphState:
        answers: list[str] = []
        fact_ids: list[str] = []
        for step_dict in state["plan_steps"]:
            scope = Scope.model_validate(step_dict["scope"])
            if step_dict["kind"] == "numeric":
                try:
                    answer, used_ids = answer_numeric_step(
                        engine, step_dict["sub_question"], scope.ciks[0], scope.fiscal_years
                    )
                except FactNotFound as exc:
                    answer = f"Cannot answer '{step_dict['sub_question']}': {exc}"
                    used_ids = []
                answers.append(answer)
                fact_ids.extend(used_ids)
            else:
                candidates = hybrid_search(
                    engine,
                    step_dict["sub_question"],
                    _embed_query_lazy(step_dict["sub_question"]),
                    cik=scope.ciks[0] if len(scope.ciks) == 1 else None,
                    item_code=(scope.item_codes or [None])[0],
                )
                top = rerank(step_dict["sub_question"], candidates)
                sections = expand_to_sections(engine, top)
                answers.append(draft_narrative_answer(step_dict["sub_question"], sections, {}))

        return {"step_answers": answers, "fact_ids_used": fact_ids}

    def verify_node(state: GraphState) -> GraphState:
        draft = "\n\n".join(state["step_answers"])
        report = verify_draft(engine, draft)
        cleaned = strip_rejected_figures(draft, report)
        return {"draft": draft, "verifier_report": report.model_dump(), "final_answer": cleaned}

    workflow = StateGraph(GraphState)
    workflow.add_node("scope", scope_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("answer_steps", answer_steps_node)
    workflow.add_node("verify", verify_node)

    workflow.set_entry_point("scope")
    workflow.add_conditional_edges("scope", scope_branch, {"planner": "planner", "clarify": END})
    workflow.add_edge("planner", "answer_steps")
    workflow.add_edge("answer_steps", "verify")
    workflow.add_edge("verify", END)

    return workflow.compile(checkpointer=MemorySaver())


def _embed_query_lazy(text: str) -> list[float]:
    from stance.ingest.embed import embed_query  # deferred: needs the retrieval extra

    return embed_query(text)
