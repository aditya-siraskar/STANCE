"""Tests for the UI's live pipeline diagram state logic — importable and
testable precisely because this logic was pulled out of the Streamlit
script into its own pure module."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "ui"))

from pipeline_viz import PIPELINE_STAGES, STAGE_KEYS, render_pipeline, stage_state


def test_stage_keys_match_real_graph_node_names():
    """The diagram must track stance.agents.graph's actual LangGraph node
    names, or it would silently stop lighting up correctly if the graph
    changes. 'response' is the one deliberate exception — a virtual
    final stage with no corresponding node (there's nothing to observe
    for reaching END)."""
    import inspect

    from stance.agents.graph import build_graph

    source = inspect.getsource(build_graph)
    real_node_names = {"scope", "planner", "router", "answer_steps", "verify"}
    for name in real_node_names:
        assert f'"{name}"' in source, f"graph.py no longer has a node called '{name}'"

    assert set(STAGE_KEYS) == real_node_names | {"response"}


def test_pending_before_anything_runs():
    for stage in PIPELINE_STAGES:
        assert stage_state(stage["key"], completed=[], active=None) == "pending"


def test_active_stage_is_active_not_pending_or_done():
    assert stage_state("planner", completed=["scope"], active="planner") == "active"


def test_earlier_stages_are_done_while_a_later_one_is_active():
    assert stage_state("scope", completed=["scope"], active="planner") == "done"


def test_clarification_stop_renders_scope_as_warn_not_done():
    """Scope-only completion with nothing active means the AmbiguousScope
    branch fired — a correct refusal to guess, rendered distinctly from
    a normal successful 'done' stage."""
    assert stage_state("scope", completed=["scope"], active=None) == "warn"


def test_full_run_scope_is_done_not_warn():
    """Scope must NOT render as 'warn' once later stages have also
    completed — 'warn' only means the run stopped at scope."""
    full_run = ["scope", "planner", "router", "answer_steps", "verify", "response"]
    assert stage_state("scope", completed=full_run, active=None) == "done"


def test_render_pipeline_produces_one_box_per_stage():
    html = render_pipeline(completed=[], active=None)
    assert html.count('class="stage ') == len(PIPELINE_STAGES)


def test_render_pipeline_marks_connector_done_only_between_completed_stages():
    html = render_pipeline(completed=["scope", "planner"], active="router")
    # exactly one connector should be fully "done" (after scope, which is
    # done) — the one after planner is also done, the rest are not.
    assert html.count('class="connector done"') == 2


def test_render_pipeline_highlights_used_substage_only():
    numeric_only_steps = [{"kind": "numeric"}]
    html = render_pipeline(completed=["scope", "planner", "router"], active="answer_steps",
                            plan_steps=numeric_only_steps)
    assert 'substage used">Numeric' in html
    assert 'substage unused">Narrative' in html
