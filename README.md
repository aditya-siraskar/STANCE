# STANCE

**S**EC **T**ext **a**nd Accounting **N**umeric **C**hecking **E**ngine —
an agentic research copilot over SEC filings where narrative comes from
retrieved text, every number comes from a structured fact table, and the
language model never performs arithmetic.

See [`KAGGLE_BUILD_PLAN.md`](KAGGLE_BUILD_PLAN.md) for the current build plan
(Kaggle notebooks + Neon Postgres, small-scale, 6 phases) and
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) for the full GCP deployment
plan this project graduates into once the agents are proven end-to-end.

## Status

All 6 phases scaffolded and unit-tested locally (44 tests, ruff-clean).
**Not yet run against a live Neon database or real LLM API keys** — that
requires the one-time setup in "Running it" below, done on Kaggle.

| Phase | Notebook | Package modules | Local test status |
|---|---|---|---|
| 0 — Setup & schema | `00_setup_and_schema.ipynb` | `config`, `contracts`, `db`, `seed` | tested |
| 1 — Ingestion | `01_ingestion.ipynb` | `ingest/acquire`, `parse`, `segment`, `chunk`, `embed`, `facts` | parse/segment/chunk/facts/acquire tested; `embed` needs live run |
| 2 — Retrieval | `02_retrieval.ipynb` | `retrieval/hybrid`, `rerank`, `expand` | `expand` tested; `hybrid`/`rerank` need a live DB |
| 3 — Numeric layer | `03_numeric_layer.ipynb` | `numeric/resolver`, `calculator`, `sandbox`, `executor`, `interpret` | fully tested (sandbox/executor/interpret run against mocked facts) |
| 4 — Agent graph | `04_agent_graph.ipynb` | `agents/scope`, `router`, `planner`, `writer`, `graph`, `llm` | tested with mocked LLM/DB calls, incl. real LangGraph execution |
| 5 — Verifier & eval | `05_verifier_and_eval.ipynb` | `agents/verifier`, `eval/run_eval.py` | verifier tested incl. the injection-defeat case; `run_eval.py` needs a live run |

## Running it

1. Create a [Neon](https://neon.tech) project, enable the `vector` extension.
2. Push this repo to GitHub (public or accessible to your Kaggle account).
3. In each notebook, set `REPO_URL` to your repo's clone URL.
4. In Kaggle: **Settings > Internet > On**, then add Secrets:
   `NEON_DATABASE_URL`, `GROQ_API_KEY`, `GOOGLE_AI_API_KEY`.
5. Run notebooks `00` through `05` in order — each depends on data the
   previous one wrote to Neon.

## Local dev

```bash
pip install -e ".[dev]"                    # core + test tooling, fast (~seconds)
pip install -e ".[dev,retrieval,agents]"   # + embeddings/reranker/LangGraph/LiteLLM (pulls torch, slow)
cp .env.example .env                       # fill in NEON_DATABASE_URL etc.
pytest -q
ruff check stance tests eval
```

## Package layout

- `stance/config.py` — settings (Kaggle Secrets or `.env`)
- `stance/contracts.py` — typed inter-agent contracts (`Scope`, `Plan`,
  `ComputationSpec` — no numeric output field, `VerifierReport`)
- `stance/db.py` — Neon schema (chunks + XBRL facts, one database)
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

Notebooks in `notebooks/` are thin drivers that call into `stance/` — they
contain no logic of their own, which is what lets this port to GCP later
without a rewrite (see `IMPLEMENTATION_PLAN.md`).

## Known scope simplifications (see code comments for the "why")

- **Router is a deterministic rule**, not a second LLM call — it triages
  off the planner's own typed step structure. One fewer model round trip,
  same routing behaviour.
- **Numeric answers are always deterministic**, in both the fast and full
  route — an LLM only ever drafts narrative prose, never a figure.
- **"Ambiguous ticker" (T1.2) is represented as "no watchlist match"**
  rather than a genuine cross-company EDGAR name collision, since the
  watchlist is a fixed 5 companies at this project's scale.
- **`cagr` and multi-operand `sum`** are implemented in the sandbox but not
  wired into `interpret.py`'s keyword router — `growth_rate` and `margin`
  cover the golden set's numeric questions at this scale.
