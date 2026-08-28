# STANCE — Solution Design Document (Brief)

**Equity & Credit Research Copilot with Numeric Verification**

> Narrative comes from retrieved text, numbers come from a structured store, and the LLM never does arithmetic.

---

## 1. Document Control
- **v0.1**, 2026-08-28, Author: Aditya Siraskar. Academic Supervisor & Technical Reviewer sign-off pending.
- **Glossary highlights:** EDGAR (SEC filing repository) · CIK (filer ID) · Accession Number (filing ID) · XBRL Fact (atomic tagged number) · RAG / Hybrid retrieval / RRF / Cross-encoder reranker · Parent–child chunking · ComputationSpec (typed op, never a number) · Sandbox (whitelisted op registry) · VerifierReport · Triage/fast path · HITL · Golden set · halfvec · HNSW · OTel GenAI semconv · OWASP LLM01.

---

## 2. Executive Summary & Context

**Problem:** LLMs hallucinate numbers when asked for filing figures or to compute ratios — fluently and silently.

**Solution:** Narrative claims cite `(accession_no, item_code)`. Every number is resolved from an XBRL fact table by ID or computed via a typed `ComputationSpec` in a deterministic sandbox. A separate verifier re-derives every published figure before release.

**Defensible claim:** Numeric hallucination is structurally impossible, not statistically unlikely — the LLM never has the capability to emit a number.

**Scope — In:** Offline SEC ingestion (12 companies × 3 years, 10-K/10-Q, ~130 filings); online query pipeline (scope→plan→route→retrieve→compute→draft→verify); numeric verification with `VerifierReport`; 60–100 question eval harness with CI gate; prompt-injection defence demo; GCP Always-Free deployment.

**Scope — Out:** Transcripts/alt-data, 8-Ks, real-time prices, trading/advice, multi-tenant prod, polished frontend, non-US/non-XBRL filers, Kubernetes.

**Audience map:** Engineers → §3–6; Data eng → §4.2/§5; DevOps → §8/§10; Security → §7; QA → §4.2/§9/§11; Academics → §2/§4/§9/§11.

---

## 3. High-Level Architecture

- **System context:** Public sources (EDGAR, XBRL data sets, yfinance) → STANCE (ingestion plane → storage plane, one Postgres DB → query plane, agentic → presentation: FastAPI/Arq/Streamlit) → analyst via OIDC; observability via OTel to Cloud Trace + Langfuse.
- **Containers (GCP Always-Free):** Cloud Scheduler → Cloud Run Job (ingest) → Cloud Storage; GCE `e2-micro` running Postgres 17+pgvector+Redis (one DB); Cloud Run services `stance-api`/`stance-worker`/`stance-ui`; Secret Manager; Artifact Registry; all LLM calls via LiteLLM gateway (Groq, AI Studio, DeepSeek, OpenRouter, Ollama dev).
- **Query pipeline:** Scope (deterministic ticker→CIK, no LLM) → Planner (typed `PlanStep[]`) → Router (fast path: simple numeric lookup, small model, no retrieval; full path: hybrid retrieval + rerank) → Calculator (emits `ComputationSpec`, never a number) → Sandbox (resolves facts, executes) → Writer (prose + citations) → Verifier (independent re-derivation) → Trace persistence.
- **Tech stack:** LangGraph (orchestration) · Prefect 3 (ingestion) · Cloud Scheduler/Run Jobs (scheduling) · FastAPI+Pydantic v2 · Arq/Redis (workers) · Postgres 17 + pgvector (HNSW) + tsvector (single DB for both vectors and facts) · `bge-reranker-base` ONNX INT8 · `bge-small-en-v1.5` 384-dim embeddings · LiteLLM gateway · tiered models (fast/synthesis/planning-verification) · whitelisted sandbox · Streamlit UI · Cloud Run + 1× e2-micro · Terraform · GitHub Actions CI/CD · OTel→Cloud Trace+Langfuse · Secret Manager.
- **Free-tier substitutions:** Cloud SQL→VM Postgres, Memorystore→VM Redis, Vertex AI→LiteLLM free providers, hosted embed/rerank→local CPU, IAP→in-app OIDC, self-hosted Langfuse→Langfuse Cloud hobby.

---

## 4. Component / Module Design

**Modules:** `stance_common` (shared contracts/logging) · `stance_ingest` (acquire/parse/segment/chunk/embed/facts/flows) · `stance_retrieval` (hybrid/rerank/expand) · `stance_agents` (graph/scope/planner/router/fastpath/calculator/sandbox/writer/verifier) · `stance_llm` (model routing policy) · `stance_api` (FastAPI + worker) · `apps/ui` (Streamlit) · `eval` (golden set, injection corpus, CI gate).

**Ingestion plane:** Acquire (idempotent EDGAR/XBRL pull) → Parse & segment (Item 1A/7/7A/8 boundaries — the single biggest retrieval-quality lever) → Chunk (parent–child, tables preserved) → Metadata tagging (CIK, form, period, section) → two destinations: vector store (chunks) and relational fact table (`xbrl_facts`, source of truth) → versioning stamps for controlled re-embeds.

**Query plane:** Scope resolution (deterministic) → Planner (typed sub-questions, narrative/numeric) → Router/triage (simple numeric → fast path; else full path) → Retrieval (hybrid BM25+dense, RRF, metadata prefilter, rerank top50→top8, expand to parent) → Calculator (emits `ComputationSpec` only) → Sandbox (resolves fact IDs, whitelisted ops, `FactNotFound` fails loudly) → Writer (cites + references specs) → Verifier (independent re-derivation, tolerance check, strips unresolved) → Trace persistence.

**Sequence:** Full path runs scope→plan→route→retrieve→rerank→expand→compute→verify→persist, each step logged. Fast path skips retrieval and the frontier model entirely: scope→plan→route→direct fact lookup→small-model format→verify→persist.

---

## 5. Data & Database Design

**ER:** `companies` → `filings` → `sections` → `chunks` (with `parent_chunk`); `filings` → `xbrl_facts` (aliased via `fact_aliases`); standalone `query_traces` audit table. One database — citation-to-figure joins are plain SQL.

**Schema (core tables):** `companies`, `filings` (citation targets), `sections` (item-coded), `chunks` (halfvec(384) embedding + tsvector + denormalised filter metadata), `xbrl_facts` (source of truth: element, value, unit, period, segment_axis, source_url), `fact_aliases` (deterministic concept resolution), `query_traces` (full audit JSON).

**Indexes:** HNSW on embeddings, GIN on tsvector, composite indexes on chunk/fact filter columns.

**Data flow:** Enter via daily EDGAR poll + quarterly XBRL bulk pull → process (parse/segment/chunk/embed + XBRL extraction) → rest in Postgres (chunks/facts/traces) + Cloud Storage (raw/parsed) → read at query time by retrieval agent and sandbox; verifier re-reads independently.

**Retention:** No legacy migration; versioned re-embedding (never in-place rebuild); HNSW built offline and restored; nightly `pg_dump` backups; raw filings retained indefinitely (~1.5GB); Cloud SQL migration is a one-variable Terraform change.

---

## 6. API & Integration Design

**Internal APIs:** `POST /query` (sync, fast path) · `POST /query/async` + `GET /query/{job_id}` (long queries) · `GET /trace/{trace_id}` (full audit) · `GET /facts/{fact_id}` (citation target) · `GET /health`.

**Key contracts:** `PlanStep` (typed sub-question + scope + kind) and `ComputationSpec` (operation + fact-ID operands, never emits a number).

**Errors:** 400/401/403/404/422 standard; 429 provider rate limit after fallback exhausted; 503 daily budget cap; `FactNotFound` surfaces as a rejected figure in `VerifierReport`, not a fabricated value.

**External integrations:** SEC EDGAR daily index (polite rate limits, idempotent) · SEC XBRL bulk data sets · yfinance (best-effort, degrades to `FactNotFound`) · LiteLLM→Groq/AI Studio/DeepSeek/OpenRouter/Ollama (fallback chain, spend caps, circuit breaker) · Langfuse Cloud (dual export with Cloud Trace) · Google OIDC.

**Messaging:** Single Arq queue (`stance:queries`); graph state checkpointed in Postgres so workers resume, not replay. Ingestion is scheduled, not event-driven.

---

## 7. Security & Compliance

- **AuthN/Z:** Google OIDC, server-verified, email allow-list; Cloud Run `--no-allow-unauthenticated`; in-app auth chosen over IAP (cheaper, CI-testable); RLS policies written/tested (single-tenant in practice); WIF for CI (no static keys).
- **Data security:** TLS everywhere; AES-256 at rest; DB/Redis firewalled to Cloud Run egress only; sandbox has no network/filesystem access and a hard timeout; fact resolution happens outside the sandbox.
- **Prompt injection (OWASP LLM01):** Test suite plants instructions in filing text; defences — structured tool contracts, untrusted-text delimiting, output schema validation, and (the key one) verifier re-derivation strips any number lacking a `fact_id`. **The numeric architecture is itself the injection defence.**
- **Compliance:** Public data only, no PII; declared EDGAR User-Agent and rate limits; explicitly "not investment advice"; only public filing text sent to model providers.
- **Secrets:** Secret Manager, ~5 secrets, rotated by replacement.

---

## 8. Infrastructure & Deployment

**Resources (GCP Always-Free):** 1× `e2-micro` VM (Postgres+pgvector+Redis via Docker Compose) · Cloud Run (`api`/`worker`/`ui`, scale-to-zero) · Cloud Run Job (daily ingest) · Cloud Storage (5GB) · Artifact Registry (0.5GB) · Cloud Scheduler · Secret Manager · Cloud Trace/Logging.

**Non-negotiable constraint:** `e2-micro` = 1GB RAM / 2 shared vCPU. Mitigations: 2GB swapfile, tuned Postgres memory params, HNSW built offline and restored, `halfvec(384)` quantisation.

**Network:** No load balancer/API gateway (cost); Cloud Run authenticates at app layer; VM firewalled to Cloud Run egress only.

**CI/CD:** Trunk-based; PR → lint/type-check/tests → **eval gate** (blocks merge on golden-set regression) → merge → build/push → `gcloud run deploy` → migrate. Terraform plan reviewed before every apply.

---

## 9. Non-Functional Requirements

- **Performance:** Fast path ≤2s p50; full path ≤8s/≤20s p50/p95; reranker 200–400ms; cold start 3–6s (mitigated by warm ping); 20 concurrent queries; cost/latency reported **per triage path**, not averaged.
- **Availability:** Best-effort, single-region, no SLA claimed (Always-Free VM is a deliberate SPOF); idempotent ingestion; checkpointed graph state; LiteLLM fallback + circuit breaker; RPO ≈24h / RTO ≈1–2h via nightly backups; demo resilience via cached answers + backup video.
- **Correctness (the key NFR):** Hallucinated-figure rate before/after verification (headline metric) · citation coverage · verifier rejection rate · numeric accuracy vs. golden set · retrieval quality (hit@8/MRR/nDCG@8) · abstention accuracy on unanswerable questions · injection attack success rate (naive vs. defended).
- **Golden set:** 60–100 questions, stratified across single-fact numeric, multi-step computation, single/multi-company narrative, cross-period trend, and adversarial/unanswerable; CI-gated; runs in <15 min.

---

## 10. Observability

- **Logging:** Structured JSON to Cloud Logging, correlated by `trace_id`; every query persists a full `query_traces` row (plan, route, chunks, specs, verifier report, tokens, cost, latency).
- **Metrics:** OTel GenAI semconv spans → Cloud Trace + Langfuse Cloud. Dashboards: per-stage latency, tokens/cost by model tier and triage path, retrieval quality, citation coverage, **verifier rejection rate**, budget vs. cap.
- **Alerting:** Verifier rejection-rate spike (primary quality signal) · ingestion job failure · daily spend cap (circuit breaker) · billing >$1 (free-tier tripwire) · VM memory/connection saturation. Single-operator: email alerts, weekly cost check.

---

## 11. Assumptions, Dependencies & Risks

**Key dependencies:** SEC EDGAR (sole corpus source) · free-tier model providers (rate-limit risk, mitigated by fallback + cached demo) · yfinance (fails loudly, never estimates) · GCP Always-Free · Langfuse/Prefect Cloud (non-critical) · pinned OSS libraries.

**Key assumptions:** Free-tier limits audited and dated; scoped 12×3 corpus is a deliberate methodology choice; XBRL tagging hand-verified across the watchlist; segmentation has a confidence score + manual overrides; single-operator/tenant/region; demo-scale query volume.

**Top risks:** `e2-micro` OOM under HNSW load (High/Severe — swapfile, halfvec, offline index build) · free-tier rate limits during demo (High/Severe — caching, fallback chain, backup video) · scope creep (High/Severe — cut-list below) · segmentation/XBRL edge cases (Medium — confidence scores, overrides) · cold start (Medium — warm ping) · pgvector filtered-query under-retrieval (Medium — Qdrant fallback documented) · corpus loss (Low/Severe — nightly backups).

**Cut-list (in order):** 1) alt-data/transcripts, 2) Next.js frontend (Streamlit stays), 3) 8-K support, 4) multi-tenant onboarding (RLS policies kept), 5) extra ablation rows.

**Never cut:** verifier, eval harness, fact table, injection demo — these are the contribution.

---

## Appendices

- **A — Build order:** Wks 1–3 ingestion/retrieval → 4–5 numeric layer/structured store → 6–7 agent graph → 8–9 verification + eval harness (headline) → 10–12 deployment/security/injection demo.
- **B — Data sources:** SEC EDGAR (full-text + daily index), SEC XBRL Financial Statement Data Sets, yfinance — all free, no key.
- **C — Related docs:** `IMPLEMENTATION_PLAN.md`, `docs/free-tier-audit.md`, `docs/design-decisions.md`, `docs/data-dictionary.md`, `docs/threat-model.md`, `eval/thresholds.yaml`, generated OpenAPI spec.
