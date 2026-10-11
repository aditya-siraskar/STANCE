"""Pure HTML-generation logic for the live pipeline diagram — kept out of
app.py (a Streamlit script that can't itself be imported outside a
Streamlit runtime) so the state-transition rules (pending/active/done/warn,
which connectors fill in) are actually unit-testable.

The stage `key`s must match stance.agents.graph's real LangGraph node
names exactly ("response" is the one exception: a virtual final stage
lit up after "verify" completes, since there's no observable node for
reaching END). app.py drives this from graph.stream()'s real per-node
completion events — this module only renders a given (completed, active)
snapshot, it has no opinion on how that snapshot was produced.
"""
from __future__ import annotations

PIPELINE_STAGES = [
    {"key": "scope", "icon": "\U0001F9ED", "label": "Scope", "sub": "ticker + period, no LLM"},
    {"key": "planner", "icon": "\U0001F9E0", "label": "Planner", "sub": "LLM decomposition"},
    {"key": "router", "icon": "\U0001F500", "label": "Router", "sub": "deterministic triage"},
    {"key": "answer_steps", "icon": "⚙️", "label": "Execute", "sub": "numeric | retrieval+writer"},
    {"key": "verify", "icon": "✅", "label": "Verifier", "sub": "re-derives every figure"},
    {"key": "response", "icon": "\U0001F4EC", "label": "Response", "sub": "cited answer"},
]

STAGE_KEYS = [s["key"] for s in PIPELINE_STAGES]


def stage_state(key: str, completed: list[str], active: str | None) -> str:
    """Returns 'active' | 'done' | 'warn' | 'pending' for one stage key.

    'warn' is the clarification-branch outcome: scope legitimately
    completed and nothing downstream ever ran, which is a correct
    "refused to guess" result, not a failure — rendered distinctly from
    a normal 'done' so it reads as "stopped here on purpose".
    """
    if key == active:
        return "active"
    if key in completed:
        is_clarification_stop = key == "scope" and completed == ["scope"] and active is None
        return "warn" if is_clarification_stop else "done"
    return "pending"


def render_pipeline(completed: list[str], active: str | None, plan_steps: list[dict] | None = None) -> str:
    boxes = []
    for i, stage in enumerate(PIPELINE_STAGES):
        key = stage["key"]
        state = stage_state(key, completed, active)

        sub_html = f'<div class="stage-sub">{stage["sub"]}</div>'
        if key == "answer_steps" and plan_steps and state in ("active", "done"):
            kinds = {s["kind"] for s in plan_steps}
            numeric_cls = "used" if "numeric" in kinds else "unused"
            narrative_cls = "used" if "narrative" in kinds else "unused"
            sub_html = (
                f'<div class="substage-row">'
                f'<span class="substage {numeric_cls}">\U0001F522 numeric</span>'
                f'<span class="substage {narrative_cls}">\U0001F4C4 narrative</span>'
                f'</div>'
            )

        boxes.append(
            f'<div class="stage {state}">'
            f'<div class="stage-icon">{stage["icon"]}</div>'
            f'<div class="stage-label">{stage["label"]}</div>'
            f'{sub_html}'
            f'</div>'
        )
        if i < len(PIPELINE_STAGES) - 1:
            connector_done = "done" if state == "done" else ""
            boxes.append(f'<div class="connector {connector_done}"></div>')

    return (
        '<div class="pipeline-wrap">'
        '<div class="pipeline-title">Agent Pipeline</div>'
        f'<div class="pipeline">{"".join(boxes)}</div>'
        '</div>'
    )
