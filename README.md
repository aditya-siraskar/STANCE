# STANCE

**S**EC **T**ext **a**nd Accounting **N**umeric **C**hecking **E**ngine —
an agentic research copilot over SEC filings where narrative comes from
retrieved text, every number comes from a structured fact table, and the
language model never performs arithmetic.

Runs entirely **locally**: Postgres + pgvector in Docker, 5 notebooks that
build the corpus and prove each agent, and a Streamlit UI to demo the
whole thing end to end.

See [`LOCAL_BUILD_PLAN.md`](LOCAL_BUILD_PLAN.md) for the phase-by-phase
build plan and [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) for the
full GCP deployment plan this project graduates into afterward.

## Quickstart

```bash
docker compose up -d                        # local Postgres + pgvector
pip install -e ".[dev,retrieval,agents,ui]"  # pulls torch — slow once
cp .env.example .env                        # fill in GROQ_API_KEY etc.
```

Then run the notebooks **in order** — each depends on data the previous
one wrote:

| Notebook | What it does |
|---|---|
| `notebooks/01_setup_and_ingestion.ipynb` | Creates the schema, seeds the 5-company watchlist, ingests 10-Ks (parse/segment/chunk/embed), extracts XBRL facts |
| `notebooks/02_retrieval.ipynb` | Hybrid (dense+FTS+RRF) retrieval, reranking ablation |
| `notebooks/03_numeric_layer.ipynb` | Resolver/calculator/sandbox, including the two failure-mode test cases that prove the design |
| `notebooks/04_agent_graph.ipynb` | Full LangGraph pipeline on 5 mixed questions |
| `notebooks/05_verifier_and_eval.ipynb` | Golden-set eval + the injection-defence demo |

Then launch the demo UI:

```bash
streamlit run apps/ui/app.py
```

Open http://localhost:8501 — it has **Ask**, **Trace**, **Verification**,
and **Evaluation** tabs, each with inline explanation of what it's showing
and why. A sidebar checklist tells you if the corpus isn't ingested yet.

## .env

Only `GROQ_API_KEY` is required to get the agent graph running (Groq's
free tier). `DATABASE_URL` already defaults to match `docker-compose.yml`
— you don't need to set it unless you're running a different Postgres.
`GOOGLE_AI_API_KEY` / `DEEPSEEK_API_KEY` are optional alternate providers
— see `stance/llm.py`'s `NODE_POLICY` to route a node to one of them.

## Stopping / resetting

```bash
docker compose down          # stop Postgres, keep data
docker compose down -v       # stop Postgres, DELETE all ingested data
```

## Local dev

```bash
pip install -e ".[dev]"                           # core + test tooling, fast (~seconds)
pip install -e ".[dev,retrieval,agents,ui]"        # + embeddings/reranker/LangGraph/LiteLLM/Streamlit
pytest -q
ruff check stance tests eval apps
```

## Package layout

- `stance/config.py` — settings (`.env`, defaults match `docker-compose.yml`)
- `stance/contracts.py` — typed inter-agent contracts (`Scope`, `Plan`,
  `ComputationSpec` — no numeric output field, `VerifierReport`)
- `stance/db.py` — Postgres schema (chunks + XBRL facts, one database)
- `stance/seed.py` — watchlist (5 companies) + concept→XBRL-tag aliases
- `stance/ingest/` — acquire (EDGAR), parse (iXBRL→text), segment (Item
  1A/7/7A/8), chunk (parent-child), embed (bge-small), facts (XBRL→table)
- `stance/retrieval/` — hybrid (dense+FTS+RRF), rerank (cross-encoder),
  expand (child→parent)
- `stance/numeric/` — resolver (concept→fact_id, no LLM), calculator
  (emits `ComputationSpec`), sandbox (whitelisted ops), executor (ties
  specs to resolved facts), interpret (keyword→concept/operation mapping)
- `stance/agents/` — scope (deterministic entity/period resolution),
  planner (LLM decomposition), router (deterministic triage), writer
  (deterministic fast-path formatting + LLM narrative drafting), verifier
  (re-derives every cited figure), graph (LangGraph assembly)
- `stance/llm.py` — LiteLLM per-node model routing policy
- `eval/` — golden set (20 Q, stratified incl. an unanswerable stratum),
  injection payloads, `run_eval.py` driver
- `apps/ui/app.py` — Streamlit demo (Ask / Trace / Verification / Evaluation)

Notebooks in `notebooks/` are thin drivers that call into `stance/` — they
contain no logic of their own, which is what lets this port to GCP later
without a rewrite (see `IMPLEMENTATION_PLAN.md`).

## Known scope simplifications (see code comments for the "why")

- **Router is a deterministic rule**, not a second LLM call — it triages
  off the planner's own typed step structure. One fewer model round trip,
  same routing behaviour.
- **Numeric answers are always deterministic**, in both the fast and full
  route — an LLM only ever drafts narrative prose, never a figure.
- **"Ambiguous ticker" (T1.2)** is represented as "no watchlist match"
  rather than a genuine cross-company EDGAR name collision, since the
  watchlist is a fixed 5 companies at this project's scale.
- **`cagr` and multi-operand `sum`** are implemented in the sandbox but not
  wired into `interpret.py`'s keyword router — `growth_rate` and `margin`
  cover the golden set's numeric questions at this scale.
