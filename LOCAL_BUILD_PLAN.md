# STANCE — Local Build Plan (Phase 1 of 2: prove it works end-to-end)

**Strategy:** build and prove the whole agent system locally — Postgres +
pgvector in Docker, 5 notebooks, and a Streamlit UI — before porting the
same `stance/` package to GCP (`e2-micro` + Cloud Run) as a second stage.
No cloud database, no notebook-platform lock-in: everything runs on your
own machine.

**Scale:** 5 companies × 2 fiscal years, 10-K only → ~10 filings, ~4–6k
chunks. Enough to prove multi-company comparison, retrieval, numerics,
verification — small enough to ingest in minutes on a laptop GPU/CPU.

Watchlist: AAPL, MSFT, JPM, XOM, PFE — 5 sectors, FY23–FY24.

---

## Why local Postgres instead of a managed service

A local Postgres + pgvector container, matching `docker-compose.yml`,
keeps the entire system reproducible with `docker compose up -d` and
`docker compose down -v` — no account, no cloud quota, no network
dependency once the corpus is ingested. The schema and SQL are identical
to what a managed Postgres (Cloud SQL, Neon, RDS) would run — porting
later is a one-line change to `DATABASE_URL`.

---

## Repository layout

```
stance/
├── docker-compose.yml              # local Postgres + pgvector
├── stance/                         # the importable package — ALL logic lives here
│   ├── config.py                   # pydantic-settings: .env, defaults match docker-compose
│   ├── contracts.py                # Scope, PlanStep, ComputationSpec, VerifierReport
│   ├── db.py                       # engine + session, schema DDL
│   ├── ingest/
│   │   ├── acquire.py               # EDGAR fetch, rate-limited, cached to data/raw/
│   │   ├── parse.py                 # iXBRL → clean text
│   │   ├── segment.py               # Item 1A/7/7A/8 boundaries
│   │   ├── chunk.py                 # parent-child chunking
│   │   ├── embed.py                 # bge-small-en-v1.5
│   │   └── facts.py                 # XBRL facts → xbrl_facts table
│   ├── retrieval/
│   │   ├── hybrid.py                 # dense + FTS + RRF
│   │   ├── rerank.py                 # bge-reranker-base
│   │   └── expand.py                 # child -> parent section
│   ├── numeric/
│   │   ├── resolver.py               # concept → fact_id (fact_aliases, no LLM)
│   │   ├── calculator.py             # emits ComputationSpec
│   │   ├── sandbox.py                # whitelisted op registry executor
│   │   ├── executor.py               # ties specs to resolved facts
│   │   └── interpret.py              # keyword → concept/operation mapping
│   ├── agents/
│   │   ├── scope.py                  # ticker→CIK, period resolution (no LLM)
│   │   ├── planner.py
│   │   ├── router.py
│   │   ├── writer.py
│   │   ├── verifier.py
│   │   └── graph.py                  # LangGraph assembly
│   └── llm.py                        # LiteLLM router (Groq / Gemini / DeepSeek)
├── notebooks/
│   ├── 01_setup_and_ingestion.ipynb
│   ├── 02_retrieval.ipynb
│   ├── 03_numeric_layer.ipynb
│   ├── 04_agent_graph.ipynb
│   └── 05_verifier_and_eval.ipynb
├── apps/ui/
│   └── app.py                        # Streamlit demo: Ask / Trace / Verification / Evaluation
├── eval/
│   ├── golden_set.json              # 20 Q/A, stratified
│   ├── injection_payloads.json      # injection attacks
│   └── run_eval.py
├── tests/                            # pytest, run locally + in CI
├── .github/workflows/ci.yml          # lint + test on push (no deploy yet)
├── pyproject.toml
└── README.md
```

**Rule:** notebooks and the Streamlit app call `stance.*` functions, they
do not contain logic. This is what makes a later GCP port a non-event:
the package doesn't know whether it's running in a notebook, a Streamlit
app, or a Cloud Run service.

---

## Phase 1 — Setup & Ingestion (`01_setup_and_ingestion.ipynb`)

1. `docker compose up -d` — Postgres + pgvector, matching `.env`'s default
   `DATABASE_URL`.
2. `stance/db.py`: schema DDL — `companies, filings, sections, chunks,
   xbrl_facts, fact_aliases, query_traces`. Idempotent (`IF NOT EXISTS`
   throughout; `fact_aliases` uses `UNIQUE NULLS NOT DISTINCT` so its
   company-agnostic rows, which need `cik IS NULL`, dedupe correctly on
   re-seed — a plain composite `PRIMARY KEY` would silently force `cik`
   `NOT NULL` and break this).
3. `stance/seed.py`: 5 companies, concept→XBRL-tag aliases.
4. `acquire.py`: fetch the 10 filings by known accession number (looked
   up from each company's `submissions` JSON), cached to `data/raw/`
   (git-ignored).
5. `parse.py` + `segment.py`: strip iXBRL noise, extract Item 1A/7/7A/8
   boundaries, preserve tables as `[TABLE]` blocks.
6. `chunk.py`: parent-child, ~500-token children, tagged with
   `cik, ticker, fiscal_year, item_code, accession_no`.
7. `embed.py`: `bge-small-en-v1.5` (CPU or GPU), write to
   `chunks.embedding` (384-dim).
8. `facts.py`: pull each company's `companyfacts` JSON, extract revenue,
   net income, total assets, EPS for FY23/FY24 into `xbrl_facts`.

**Exit criteria:** `chunks` and `xbrl_facts` non-zero for all 5 companies;
a hand-check of one company's revenue fact matches its 10-K.

---

## Phase 2 — Retrieval (`02_retrieval.ipynb`)

1. `hybrid.py`: dense cosine (pgvector) + Postgres FTS, fused with RRF,
   metadata-prefiltered on `cik`/`item_code`.
2. `rerank.py`: `bge-reranker-base` over top-15 → top-5.
3. Ablation: dense-only vs. RRF vs. RRF+rerank on hand-written queries.

**Exit criteria:** an Item-1A-scoped query returns only Item 1A chunks;
the ablation shows RRF+rerank ≥ dense-only.

---

## Phase 3 — Numeric layer (`03_numeric_layer.ipynb`)

1. `resolver.py`: deterministic `resolve(concept, cik, fiscal_year) ->
   fact_id`, raises `FactNotFound` if absent.
2. `calculator.py`: emits a `ComputationSpec` — schema has no numeric
   field.
3. `sandbox.py`: whitelisted op registry, unit/period compatibility
   checks.
4. Demo both failure modes: a clean growth-rate computation, and a
   missing-fact case failing loudly.

**Exit criteria:** 5 numeric questions computed correctly with `fact_id`
provenance; one deliberately-impossible question raises `FactNotFound`.

---

## Phase 4 — Agent graph (`04_agent_graph.ipynb`)

1. `scope.py`: ticker→CIK, period resolution, deterministic.
2. `planner.py`: LLM (Groq/Gemini/DeepSeek via `stance/llm.py`) emits a
   typed `Plan`.
3. `router.py`: deterministic triage off the planner's typed output.
4. `writer.py`: drafts prose with citations + `{{spec_id}}` placeholders
   for narrative steps; numeric steps are always formatted deterministically.
5. `graph.py`: LangGraph — `scope -> planner -> router -> answer_steps ->
   verify`, `MemorySaver` checkpointer.

**Exit criteria:** 5 mixed questions traverse the graph correctly,
including one unresolvable-entity case that stops at a clarification
instead of guessing.

---

## Phase 5 — Verifier & eval (`05_verifier_and_eval.ipynb`)

1. `verifier.py`: re-derives every cited figure against `xbrl_facts`,
   strips anything untraceable, emits `VerifierReport`.
2. `eval/golden_set.json`: 20 Q/A across numeric / narrative / comparison
   / trend / unanswerable — run through the full graph.
3. **Injection demo**: a fabricated `fact_id` citation is rejected because
   it doesn't resolve — the numeric architecture *is* the injection
   defence.
4. Headline table: hallucinated-figure rate before vs. after verification.

**Exit criteria:** before/after hallucination table and the
injection-defeated demo both print correctly.

---

## Phase 6 — Streamlit UI (`apps/ui/app.py`)

A single demo surface over everything the notebooks built:

- **Ask** — question box with example-question shortcuts, routes through
  the full graph, shows the answer with a route badge.
- **Trace** — the typed plan, retrieved/computed steps, fact IDs used —
  the audit trail.
- **Verification** — the `VerifierReport` as a scorecard, rejected
  figures highlighted, plus a one-click injection-defence demo.
- **Evaluation** — runs the golden set and shows abstention accuracy,
  citation coverage, and the per-question results table.

A sidebar explains the governing rule, renders the agent pipeline as a
Graphviz diagram, and shows a live corpus-readiness checklist so a
first-time run never dead-ends on a raw stack trace.

**Exit criteria:** `streamlit run apps/ui/app.py` with no corpus ingested
shows the setup checklist, not an error; with the corpus ingested, all
four tabs work end to end.

---

## What's deliberately deferred to the GCP stage

- Cloud Run deployment, Terraform, Docker image publishing
- Arq/Redis async workers (notebooks and the UI run synchronously — fine
  at this scale)
- CI **deploy** step (CI **test/lint** step is included now)
- IAP/OIDC auth, observability stack (OTel/Langfuse/Cloud Trace)

Nothing above requires touching `stance/` package code when it's added
later — only new wrapper code (`stance_api/`, `infra/`) gets built on top.

---

## Immediate next steps

1. `docker compose up -d`
2. `pip install -e ".[dev,retrieval,agents,ui]"`
3. `cp .env.example .env` and fill in `GROQ_API_KEY`
4. Run `notebooks/01_setup_and_ingestion.ipynb`, then `02` → `05` in order
5. `streamlit run apps/ui/app.py`
