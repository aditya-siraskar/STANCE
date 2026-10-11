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
from ui_components import kpi_row

from stance.config import settings

st.set_page_config(page_title="STANCE", layout="wide")

# --------------------------------------------------------------------------
# Theme — [0A1931, 1A3D63, 4A7FA7, B3CFE5, F6FAFD], navy-to-powder-blue.
# --------------------------------------------------------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap');

    :root {
        --navy: #0A1931;
        --blue-dark: #1A3D63;
        --blue-mid: #4A7FA7;
        --blue-light: #B3CFE5;
        --bg: #F6FAFD;
        --glass: rgba(255,255,255,0.68);
        --glass-border: rgba(26,61,99,0.14);
        --shadow-soft: 0 2px 10px rgba(10,25,49,0.05), 0 8px 28px rgba(10,25,49,0.06);
        --shadow-lift: 0 4px 16px rgba(10,25,49,0.08), 0 14px 36px rgba(10,25,49,0.10);
        --mono: 'JetBrains Mono', ui-monospace, 'SF Mono', monospace;
    }

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .stApp {
        background:
            radial-gradient(circle at 10% 0%, rgba(179,207,229,0.35) 0%, transparent 45%),
            radial-gradient(circle at 90% 10%, rgba(74,127,167,0.12) 0%, transparent 40%),
            var(--bg);
    }
    h1, h2, h3, h4 { color: var(--navy) !important; font-weight: 700 !important; }
    p, li, span, label { color: var(--navy); }

    ::-webkit-scrollbar { width: 9px; height: 9px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--blue-light); border-radius: 999px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--blue-mid); }

    .stance-hero {
        padding: 1.6rem 1.9rem; border-radius: 18px; margin-bottom: 1.25rem;
        background: linear-gradient(135deg, var(--navy) 0%, var(--blue-dark) 70%, var(--blue-mid) 140%);
        color: var(--bg); box-shadow: var(--shadow-lift);
        border: 1px solid rgba(255,255,255,0.08);
        position: relative; overflow: hidden;
    }
    .stance-hero::after {
        content: ''; position: absolute; inset: 0;
        background: radial-gradient(circle at 85% -10%, rgba(179,207,229,0.25) 0%, transparent 55%);
        pointer-events: none;
    }
    .stance-hero h1, #stance-title {
        margin: 0; font-size: 1.85rem; letter-spacing: -0.01em;
        color: #FFFFFF !important; position: relative;
    }
    .stance-hero p { margin: 0.4rem 0 0 0; color: var(--blue-light); font-size: 0.95rem; position: relative; }

    .stance-rule {
        border-left: 3px solid var(--blue-mid); padding: 0.65rem 0.95rem;
        background: var(--glass); backdrop-filter: blur(10px);
        border-radius: 0 10px 10px 0; font-size: 0.85rem;
        box-shadow: var(--shadow-soft);
    }

    /* ---- base glass-card look, applied directly to every card-like
       element below rather than via a combinable class, so no Python HTML
       generation needs to pass two class names ---- */
    .glass-card, .pipeline-wrap, .answer-card, .kpi-tile {
        background: var(--glass); backdrop-filter: blur(14px) saturate(140%);
        border: 1px solid var(--glass-border); border-radius: 16px;
        box-shadow: var(--shadow-soft);
        transition: box-shadow 0.25s ease, transform 0.25s ease;
    }

    /* ---- pipeline diagram ---- */
    .pipeline-wrap {
        padding: 1.6rem 1.3rem 1.3rem; margin-bottom: 1rem;
    }
    .pipeline-title {
        font-size: 0.74rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
        color: var(--blue-mid); margin-bottom: 1rem;
    }
    .pipeline { display: flex; align-items: center; gap: 0; flex-wrap: wrap; }
    .stage {
        flex: 1 1 120px; min-width: 110px; border-radius: 13px; padding: 0.75rem 0.5rem;
        text-align: center; position: relative; z-index: 1;
        transition: transform 0.25s ease, box-shadow 0.25s ease;
    }
    .stage-num {
        width: 24px; height: 24px; line-height: 24px; border-radius: 50%;
        font-size: 0.72rem; font-weight: 700; margin: 0 auto 0.4rem;
        font-family: var(--mono);
        background: rgba(255,255,255,0.25); color: inherit;
    }
    .stage.pending .stage-num { background: rgba(74,127,167,0.18); color: var(--blue-mid); }
    .stage-label { font-weight: 700; font-size: 0.82rem; }
    .stage-sub { font-size: 0.65rem; opacity: 0.85; margin-top: 0.15rem; }

    .stage.pending { background: rgba(238,244,249,0.7); color: var(--blue-mid); opacity: 0.65; }
    .stage.pending .stage-sub { color: var(--blue-mid); }

    .stage.active {
        background: linear-gradient(135deg, var(--blue-mid), var(--blue-dark));
        color: white; transform: scale(1.07);
        box-shadow: 0 6px 20px rgba(74,127,167,0.35);
        animation: pulseGlow 1.1s ease-in-out infinite;
    }
    .stage.active .stage-sub { color: var(--blue-light); }

    .stage.done {
        background: var(--blue-dark); color: white;
        box-shadow: 0 3px 10px rgba(26,61,99,0.25);
        animation: popIn 0.35s ease-out;
    }
    .stage.done .stage-sub { color: var(--blue-light); }

    .stage.warn {
        background: var(--navy); color: white;
        box-shadow: 0 3px 10px rgba(10,25,49,0.3);
        animation: popIn 0.35s ease-out;
    }
    .stage.warn .stage-sub { color: var(--blue-light); }

    .connector { flex: 0 0 28px; height: 3px; background: var(--blue-light); margin: 0 -2px; align-self: center; margin-top: -22px; border-radius: 2px; transition: background 0.3s ease; }
    .connector.done { background: var(--blue-dark); }

    @keyframes pulseGlow {
        0%, 100% { box-shadow: 0 0 0 0 rgba(74,127,167,0.55), 0 6px 20px rgba(74,127,167,0.35); }
        50% { box-shadow: 0 0 0 10px rgba(74,127,167,0), 0 6px 20px rgba(74,127,167,0.35); }
    }
    @keyframes popIn {
        0% { transform: scale(0.88); opacity: 0.5; }
        100% { transform: scale(1); opacity: 1; }
    }
    @keyframes breathe {
        0%, 100% { box-shadow: 0 0 0 0 rgba(26,61,99,0.35); }
        50% { box-shadow: 0 0 0 5px rgba(26,61,99,0); }
    }

    .substage-row { margin-top: 0.5rem; font-size: 0.68rem; }
    .substage { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 999px; margin: 0 0.15rem; }
    .substage.used { background: rgba(255,255,255,0.25); font-weight: 700; }
    .substage.unused { opacity: 0.35; }

    .pipeline-status { font-size: 0.82rem; color: var(--blue-mid); font-weight: 600; margin-top: 0.6rem; min-height: 1.2rem; }

    /* ---- badges / cards ---- */
    .badge {
        display:inline-block; padding: 0.22rem 0.75rem; border-radius: 999px;
        font-size: 0.76rem; font-weight: 700; letter-spacing: 0.03em;
    }
    .badge-fast { background: var(--blue-light); color: var(--navy); }
    .badge-full { background: var(--blue-mid); color: white; }
    .answer-card {
        padding: 1.2rem 1.4rem; margin-top: 0.8rem;
        font-variant-numeric: tabular-nums; font-size: 1.02rem; line-height: 1.6;
    }
    .answer-card:hover { box-shadow: var(--shadow-lift); transform: translateY(-1px); }

    /* ---- KPI tiles ---- */
    .kpi-row {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 0.75rem; margin: 0.6rem 0 1rem;
    }
    .kpi-tile {
        padding: 0.9rem 1.1rem; border-radius: 14px;
        border-left: 3px solid var(--blue-mid);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .kpi-tile:hover { transform: translateY(-2px); box-shadow: var(--shadow-lift); }
    .kpi-accent-dark { border-left-color: var(--blue-dark); }
    .kpi-label {
        font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.05em; color: var(--blue-mid); margin-bottom: 0.3rem;
    }
    .kpi-value {
        font-family: var(--mono); font-size: 1.65rem; font-weight: 700;
        color: var(--navy); font-variant-numeric: tabular-nums;
    }

    /* ---- status checklist (sidebar) ---- */
    .status-row {
        display: flex; align-items: center; justify-content: space-between;
        padding: 0.4rem 0.1rem;
    }
    .status-dot {
        display: inline-block; width: 8px; height: 8px; border-radius: 50%;
        margin-right: 0.5rem; vertical-align: middle; flex-shrink: 0;
    }
    .status-dot.ok { background: var(--blue-dark); animation: breathe 2.2s ease-in-out infinite; }
    .status-dot.pending { background: var(--blue-light); border: 1px solid var(--blue-mid); }
    .status-label { font-size: 0.85rem; flex: 1; }
    .status-text {
        font-size: 0.65rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.04em; font-family: var(--mono);
    }
    .status-text.ok { color: var(--blue-dark); }
    .status-text.pending { color: var(--blue-mid); opacity: 0.7; }

    /* ---- progressive enhancement of native Streamlit widgets ----
       These target Streamlit's documented, long-stable CSS hooks. If a
       future Streamlit version renames them, these rules simply stop
       matching and the native default styling shows instead - no
       breakage either way. */
    .stButton > button {
        border-radius: 10px !important; border: 1px solid var(--glass-border) !important;
        transition: transform 0.15s ease, box-shadow 0.15s ease !important;
        font-weight: 600 !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px); box-shadow: var(--shadow-soft);
        border-color: var(--blue-mid) !important;
    }
    [data-testid="stDataFrame"] {
        border-radius: 12px; overflow: hidden; box-shadow: var(--shadow-soft);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="stance-hero">
      <h1 id="stance-title" style="color:#FFFFFF !important; margin:0; font-size:1.75rem;">STANCE</h1>
      <p style="color:#B3CFE5 !important; margin:0.4rem 0 0 0; font-size:0.95rem;">
      <b>S</b>EC <b>T</b>ext <b>a</b>nd Accounting <b>N</b>umeric <b>C</b>hecking <b>E</b>ngine
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
    st.error("**Can't reach Postgres.**")
    st.markdown(
        "STANCE expects a local Postgres with pgvector, matching `docker-compose.yml`.\n\n"
        "```bash\ndocker compose up -d\n```\n"
        f"Connecting to: `{settings.database_url.split('@')[-1]}`"
    )
    st.stop()
except Exception as exc:  # noqa: BLE001 — any other startup failure also gets a friendly panel
    st.error(f"**Could not initialise the database connection:** {exc}")
    st.stop()

try:
    graph = _get_graph(engine)
except ModuleNotFoundError:
    st.error("**Agent dependencies aren't installed.**")
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
        status_cls = "ok" if ok else "pending"
        status_text = "done" if ok else "pending"
        st.markdown(
            f'<div class="status-row">'
            f'<span class="status-dot {status_cls}"></span>'
            f'<span class="status-label">{label}</span>'
            f'<span class="status-text {status_cls}">{status_text}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
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
    )


# --------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------

tab_ask, tab_trace, tab_verify, tab_eval = st.tabs(
    ["Ask", "Trace", "Verification", "Evaluation"]
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
            st.warning(result["clarification"])
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
        st.info("Ask a question in the **Ask** tab first.")
    else:
        result = st.session_state["last_result"]
        if "clarification" in result:
            st.info("This question stopped at scope resolution — no plan was built.")
        else:
            st.markdown("#### Plan steps")
            for i, step in enumerate(result.get("plan_steps", []), 1):
                st.markdown(f"**Step {i} — {step['kind'].title()}:** {step['sub_question']}")

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
        st.info("Ask a question in the **Ask** tab first.")
    else:
        result = st.session_state["last_result"]
        report = result.get("verifier_report")
        if not report:
            st.info("This question stopped before verification (clarification needed).")
        else:
            st.markdown(
                kpi_row([
                    ("Figures checked", str(report["figures_checked"])),
                    ("Figures traced", str(report["figures_traced"])),
                    ("Figures rejected", str(report["figures_rejected"])),
                    ("Citation coverage", f"{report['citation_coverage']:.0%}"),
                ]),
                unsafe_allow_html=True,
            )

            if report["rejected_details"]:
                st.markdown("#### Rejected figures")
                for r in report["rejected_details"]:
                    st.error(f"`{r['claimed_value']}` — {r['reason']}: {r['detail']}")
            else:
                st.success("Every cited figure traced cleanly to `xbrl_facts`.")

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

        st.markdown(
            kpi_row([
                ("Questions run", str(len(results))),
                ("Abstention accuracy",
                 f"{correctly_abstained}/{len(unanswerable)}" if unanswerable else "n/a"),
                ("Avg citation coverage",
                 f"{avg_coverage:.0%}" if avg_coverage is not None else "n/a"),
            ]),
            unsafe_allow_html=True,
        )

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
