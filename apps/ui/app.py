"""STANCE — Streamlit demo UI.

Run with:
    streamlit run apps/ui/app.py

Requires: `pip install -e ".[dev,retrieval,agents,ui]"`, `docker compose up -d`,
and a `.env` with GROQ_API_KEY set (see .env.example). Run notebooks 01-05
first to populate the corpus — this app is a window onto what they built,
not a separate pipeline.

The pipeline diagram at the top is driven by graph.stream() — each box
lights up exactly when that LangGraph node actually completes, not on a
simulated timer. See stance/agents/graph.py's docstring on why `router`
is its own node: this is the reason.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import streamlit as st
from sqlalchemy import text as sql_text
from sqlalchemy.exc import OperationalError

# Allow running this file directly (streamlit run apps/ui/app.py) without
# having pip-installed the package in editable mode.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_viz import render_pipeline

from stance.config import settings

st.set_page_config(page_title="STANCE", page_icon="\U0001F4CA", layout="wide")

# --------------------------------------------------------------------------
# Theme — [0A1931, 1A3D63, 4A7FA7, B3CFE5, F6FAFD], navy-to-powder-blue.
# --------------------------------------------------------------------------

st.markdown(
    """
    <style>
    :root {
        --navy: #0A1931;
        --blue-dark: #1A3D63;
        --blue-mid: #4A7FA7;
        --blue-light: #B3CFE5;
        --bg: #F6FAFD;
    }
    .stApp { background: var(--bg); }
    h1, h2, h3, h4 { color: var(--navy) !important; }
    p, li, span, label { color: var(--navy); }

    .stance-hero {
        padding: 1.5rem 1.75rem; border-radius: 14px; margin-bottom: 1.25rem;
        background: linear-gradient(120deg, var(--navy) 0%, var(--blue-dark) 100%);
        color: var(--bg); box-shadow: 0 6px 18px rgba(10,25,49,0.25);
    }
    .stance-hero h1 { margin: 0; font-size: 1.75rem; color: var(--bg) !important; }
    .stance-hero p { margin: 0.4rem 0 0 0; color: var(--blue-light); font-size: 0.95rem; }

    .stance-rule {
        border-left: 4px solid var(--blue-mid); padding: 0.6rem 0.9rem;
        background: rgba(74,127,167,0.08); border-radius: 0 8px 8px 0; font-size: 0.86rem;
    }

    /* ---- pipeline diagram ---- */
    .pipeline-wrap {
        background: white; border-radius: 16px; padding: 1.5rem 1.25rem 1.25rem;
        margin-bottom: 1rem; box-shadow: 0 2px 14px rgba(10,25,49,0.08);
        border: 1px solid var(--blue-light);
    }
    .pipeline-title {
        font-size: 0.78rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
        color: var(--blue-mid); margin-bottom: 0.9rem;
    }
    .pipeline { display: flex; align-items: center; gap: 0; flex-wrap: wrap; }
    .stage {
        flex: 1 1 120px; min-width: 110px; border-radius: 12px; padding: 0.7rem 0.5rem;
        text-align: center; position: relative; z-index: 1;
    }
    .stage-icon { font-size: 1.4rem; line-height: 1; margin-bottom: 0.3rem; }
    .stage-label { font-weight: 700; font-size: 0.82rem; }
    .stage-sub { font-size: 0.65rem; opacity: 0.85; margin-top: 0.15rem; }

    .stage.pending { background: #eef4f9; color: var(--blue-mid); opacity: 0.6; }
    .stage.pending .stage-sub { color: var(--blue-mid); }

    .stage.active {
        background: var(--blue-mid); color: white; transform: scale(1.06);
        animation: pulseGlow 1.1s ease-in-out infinite;
    }
    .stage.active .stage-sub { color: var(--blue-light); }

    .stage.done {
        background: var(--blue-dark); color: white;
        animation: popIn 0.35s ease-out;
    }
    .stage.done .stage-sub { color: var(--blue-light); }

    .stage.warn {
        background: var(--navy); color: white;
        animation: popIn 0.35s ease-out;
    }
    .stage.warn .stage-sub { color: var(--blue-light); }

    .connector { flex: 0 0 28px; height: 3px; background: var(--blue-light); margin: 0 -2px; align-self: center; margin-top: -22px; border-radius: 2px; }
    .connector.done { background: var(--blue-dark); }

    @keyframes pulseGlow {
        0%, 100% { box-shadow: 0 0 0 0 rgba(74,127,167,0.55); }
        50% { box-shadow: 0 0 0 9px rgba(74,127,167,0); }
    }
    @keyframes popIn {
        0% { transform: scale(0.88); opacity: 0.5; }
        100% { transform: scale(1); opacity: 1; }
    }

    .substage-row { margin-top: 0.5rem; font-size: 0.68rem; }
    .substage { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 999px; margin: 0 0.15rem; }
    .substage.used { background: rgba(255,255,255,0.25); font-weight: 700; }
    .substage.unused { opacity: 0.35; }

    .pipeline-status { font-size: 0.82rem; color: var(--blue-mid); font-weight: 600; margin-top: 0.6rem; min-height: 1.2rem; }

    /* ---- badges / cards ---- */
    .badge { display:inline-block; padding: 0.2rem 0.7rem; border-radius: 999px; font-size: 0.78rem; font-weight: 700; }
    .badge-fast { background: var(--blue-light); color: var(--navy); }
    .badge-full { background: var(--blue-mid); color: white; }
    .answer-card {
        background: white; border: 1px solid var(--blue-light); border-radius: 12px;
        padding: 1.1rem 1.3rem; margin-top: 0.8rem; box-shadow: 0 2px 10px rgba(10,25,49,0.06);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="stance-hero">
      <h1>\U0001F4CA STANCE</h1>
      <p><b>S</b>EC <b>T</b>ext <b>a</b>nd Accounting <b>N</b>umeric <b>C</b>hecking <b>E</b>ngine
      &mdash; an agentic research copilot over SEC filings.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# Startup checks — fail with a friendly fix-it panel, never a raw traceback.
# --------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def _get_engine():
    from stance.db import get_engine
    return get_engine()


@st.cache_resource(show_spinner=False)
def _get_graph(_engine):
    from stance.agents.graph import build_graph
    return build_graph(_engine)


def _corpus_counts(engine) -> dict:
    with engine.connect() as conn:
        return {
            "companies": conn.execute(sql_text("SELECT COUNT(*) FROM companies")).scalar(),
            "filings": conn.execute(sql_text("SELECT COUNT(*) FROM filings")).scalar(),
            "chunks": conn.execute(sql_text("SELECT COUNT(*) FROM chunks")).scalar(),
            "facts": conn.execute(sql_text("SELECT COUNT(*) FROM xbrl_facts")).scalar(),
        }


try:
    engine = _get_engine()
    with engine.connect() as _probe:
        _probe.execute(sql_text("SELECT 1"))
except OperationalError:
    st.error("**Can't reach Postgres.**", icon="\U0001F6A8")
    st.markdown(
        "STANCE expects a local Postgres with pgvector, matching `docker-compose.yml`.\n\n"
        "```bash\ndocker compose up -d\n```\n"
        f"Connecting to: `{settings.database_url.split('@')[-1]}`"
    )
    st.stop()
except Exception as exc:  # noqa: BLE001 — any other startup failure also gets a friendly panel
    st.error(f"**Could not initialise the database connection:** {exc}", icon="\U0001F6A8")
    st.stop()

try:
    graph = _get_graph(engine)
except ModuleNotFoundError:
    st.error("**Agent dependencies aren't installed.**", icon="\U0001F6A8")
    st.code('pip install -e ".[dev,retrieval,agents,ui]"', language="bash")
    st.stop()

counts = _corpus_counts(engine)
corpus_ready = counts["chunks"] > 0 and counts["facts"] > 0


# --------------------------------------------------------------------------
# The live pipeline diagram — rendered from graph.stream()'s actual
# per-node completion events, not a simulated progress bar. Rendering
# logic lives in pipeline_viz.py (imported above) so it's unit-testable
# outside a Streamlit runtime.
# --------------------------------------------------------------------------

pipeline_placeholder = st.empty()
status_placeholder = st.empty()

if "completed_stages" not in st.session_state:
    st.session_state["completed_stages"] = []
    st.session_state["plan_steps_for_diagram"] = None

pipeline_placeholder.markdown(
    render_pipeline(st.session_state["completed_stages"], None, st.session_state["plan_steps_for_diagram"]),
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### The governing rule")
    st.markdown(
        '<div class="stance-rule">Narrative comes from retrieved filing text. '
        "Every number comes from a structured XBRL fact table. "
        "<b>The language model never performs arithmetic.</b></div>",
        unsafe_allow_html=True,
    )

    st.markdown("### Corpus status")
    checklist = [
        ("Postgres reachable", True),
        ("Watchlist seeded", counts["companies"] >= 5),
        ("Filings ingested", counts["filings"] > 0),
        ("Chunks embedded", counts["chunks"] > 0),
        ("XBRL facts extracted", counts["facts"] > 0),
    ]
    for label, ok in checklist:
        st.markdown(f"{'✅' if ok else '⚠️'} {label}")
    if not corpus_ready:
        st.caption("Run `notebooks/01_setup_and_ingestion.ipynb` first to populate the corpus.")

    st.markdown("### Watchlist")
    with engine.connect() as conn:
        companies = conn.execute(sql_text("SELECT ticker, name FROM companies ORDER BY ticker")).all()
    for ticker, name in companies:
        st.caption(f"**{ticker}** — {name}")


if not corpus_ready:
    st.warning(
        "No ingested data yet — the Ask tab will still work, but every question will come back "
        "unresolved. Run `notebooks/01_setup_and_ingestion.ipynb` first.",
        icon="⚠️",
    )


# --------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------

tab_ask, tab_trace, tab_verify, tab_eval = st.tabs(
    ["\U0001F50D Ask", "\U0001F9ED Trace", "✅ Verification", "\U0001F4CA Evaluation"]
)

EXAMPLE_QUESTIONS = [
    "What was Apple's FY24 revenue?",
    "What was Apple's revenue growth from FY23 to FY24?",
    "What are Apple's main risk factors?",
    "Compare Apple and Microsoft FY24 revenue",
    "What were Delta's risk factors?",
]

with tab_ask:
    st.markdown(
        "Ask a question about the watchlist's 10-K filings. Numeric answers always cite a "
        "`fact_id` traceable to `xbrl_facts`; narrative answers cite a filing section. "
        "An unrecognised company returns a clarifying question rather than a guess. "
        "**Watch the pipeline above light up live as your question runs.**"
    )

    cols = st.columns(len(EXAMPLE_QUESTIONS))
    for col, q in zip(cols, EXAMPLE_QUESTIONS):
        if col.button(q, use_container_width=True, key=f"example-{q}"):
            st.session_state["question_input"] = q

    question = st.text_input(
        "Your question", key="question_input", placeholder="e.g. What was Apple's FY24 revenue?"
    )
    ask_clicked = st.button("Ask", type="primary", disabled=not question)

    if ask_clicked:
        thread_id = f"ui-{uuid.uuid4().hex[:8]}"
        completed: list[str] = []
        result: dict = {}
        plan_steps_seen: list[dict] | None = None

        pipeline_placeholder.markdown(render_pipeline([], None), unsafe_allow_html=True)

        for update in graph.stream({"question": question}, config={"configurable": {"thread_id": thread_id}}):
            node_name = next(iter(update))
            node_state = update[node_name]
            result.update(node_state)
            completed.append(node_name)
            if node_name == "planner":
                plan_steps_seen = node_state.get("plan_steps")

            status_placeholder.markdown(
                f'<div class="pipeline-status">Running: {node_name.replace("_", " ").title()}&hellip;</div>',
                unsafe_allow_html=True,
            )
            pipeline_placeholder.markdown(
                render_pipeline(completed, node_name, plan_steps_seen), unsafe_allow_html=True
            )

        if "verify" in completed:
            completed.append("response")
        pipeline_placeholder.markdown(render_pipeline(completed, None, plan_steps_seen), unsafe_allow_html=True)
        status_placeholder.empty()

        st.session_state["completed_stages"] = completed
        st.session_state["plan_steps_for_diagram"] = plan_steps_seen
        st.session_state["last_result"] = result
        st.session_state["last_question"] = question

    if "last_result" in st.session_state:
        result = st.session_state["last_result"]
        st.markdown(f"**Q:** {st.session_state['last_question']}")

        if "clarification" in result:
            st.warning(result["clarification"], icon="❓")
            st.caption(
                "STANCE refuses to guess an unresolved company or period — this is deliberate: "
                "a silently wrong entity match is worse than an explicit question."
            )
        else:
            route = result.get("route", "?")
            badge_class = "badge-fast" if route == "fast" else "badge-full"
            route_note = (
                "single-company, single-period numeric lookup — no retrieval, cheapest path"
                if route == "fast"
                else "narrative or multi-company/period — full retrieval path"
            )
            st.markdown(
                f'<span class="badge {badge_class}">{route.upper()} PATH</span> '
                f'<span style="color:#4A7FA7;font-size:0.85rem;">{route_note}</span>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="answer-card">{result.get("final_answer", "<i>(no answer produced)</i>")}</div>',
                unsafe_allow_html=True,
            )

with tab_trace:
    st.markdown(
        "The typed `Plan` the planner produced, the route the router chose, and every fact "
        "used along the way. **This is the audit trail** — nothing here is reconstructed after "
        "the fact, it's exactly the state the graph carried."
    )
    if "last_result" not in st.session_state:
        st.info("Ask a question in the **Ask** tab first.", icon="\U0001F448")
    else:
        result = st.session_state["last_result"]
        if "clarification" in result:
            st.info("This question stopped at scope resolution — no plan was built.")
        else:
            st.markdown("#### Plan steps")
            for i, step in enumerate(result.get("plan_steps", []), 1):
                kind_icon = "\U0001F522" if step["kind"] == "numeric" else "\U0001F4C4"
                st.markdown(f"{kind_icon} **Step {i}** ({step['kind']}): {step['sub_question']}")

            st.markdown("#### Per-step answers (before verification)")
            for ans in result.get("step_answers", []):
                st.code(ans, language=None)

            st.markdown("#### Fact IDs used")
            fact_ids = result.get("fact_ids_used", [])
            st.write(fact_ids if fact_ids else "_(none — this was a purely narrative answer)_")

with tab_verify:
    st.markdown(
        "The verifier re-derives every cited `fact_id` directly from `xbrl_facts`, independent "
        "of the writer's draft. A figure that doesn't resolve is **stripped before publication** "
        "— this is also the prompt-injection defence: a fabricated number has no real `fact_id`."
    )
    if "last_result" not in st.session_state:
        st.info("Ask a question in the **Ask** tab first.", icon="\U0001F448")
    else:
        result = st.session_state["last_result"]
        report = result.get("verifier_report")
        if not report:
            st.info("This question stopped before verification (clarification needed).")
        else:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Figures checked", report["figures_checked"])
            c2.metric("Figures traced", report["figures_traced"])
            c3.metric("Figures rejected", report["figures_rejected"])
            c4.metric("Citation coverage", f"{report['citation_coverage']:.0%}")

            if report["rejected_details"]:
                st.markdown("#### Rejected figures")
                for r in report["rejected_details"]:
                    st.error(f"`{r['claimed_value']}` — {r['reason']}: {r['detail']}", icon="❌")
            else:
                st.success("Every cited figure traced cleanly to `xbrl_facts`.", icon="✅")

    st.divider()
    st.markdown("#### Injection defence demo")
    st.caption(
        "Simulates a writer that WAS successfully manipulated into citing a fabricated figure, "
        "and shows the verifier stripping it before publication."
    )
    if st.button("Run injection demo"):
        with st.spinner("Running..."):
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "eval"))
            from run_eval import run_injection_demo
            injection_result = run_injection_demo(engine)
        st.markdown("**Before verification (what an unverified pipeline would publish):**")
        st.code(injection_result["draft"], language=None)
        st.markdown("**After verification:**")
        st.code(injection_result["cleaned_answer"], language=None)
        st.json(injection_result["verifier_report"])

with tab_eval:
    st.markdown(
        "Runs the 20-question golden set (numeric, narrative, comparison, trend, and an "
        "**unanswerable stratum** that should trigger abstention, not a guess) through the "
        "full graph."
    )
    if st.button("Run golden-set evaluation", type="primary"):
        with st.spinner("Running golden set (this calls the LLM for every question)..."):
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "eval"))
            from run_eval import run_golden_set
            golden_results = run_golden_set(engine)
        st.session_state["golden_results"] = golden_results

    if "golden_results" in st.session_state:
        results = st.session_state["golden_results"]
        unanswerable = [r for r in results if r.get("kind") == "unanswerable"]
        correctly_abstained = sum(1 for r in unanswerable if r.get("correctly_abstained"))
        coverages = [
            r["verifier_report"]["citation_coverage"]
            for r in results if r.get("verifier_report")
        ]
        avg_coverage = sum(coverages) / len(coverages) if coverages else None

        c1, c2, c3 = st.columns(3)
        c1.metric("Questions run", len(results))
        c2.metric(
            "Abstention accuracy",
            f"{correctly_abstained}/{len(unanswerable)}" if unanswerable else "n/a",
        )
        c3.metric("Avg citation coverage", f"{avg_coverage:.0%}" if avg_coverage is not None else "n/a")

        st.dataframe(
            [
                {
                    "id": r["id"], "kind": r["kind"], "question": r["question"],
                    "route": r.get("route", "-"), "answer": str(r.get("answer", ""))[:120],
                }
                for r in results
            ],
            use_container_width=True,
            hide_index=True,
        )
