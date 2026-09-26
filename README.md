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

Phase 0 (setup & schema) scaffolded. See `notebooks/00_setup_and_schema.ipynb`.

## Local dev

```bash
pip install -e ".[dev]"
cp .env.example .env   # fill in NEON_DATABASE_URL etc.
pytest -q
```

## Package layout

- `stance/config.py` — settings (Kaggle Secrets or `.env`)
- `stance/contracts.py` — typed inter-agent contracts (`Scope`, `Plan`,
  `ComputationSpec`, `VerifierReport`)
- `stance/db.py` — Neon schema (chunks + XBRL facts, one database)
- `stance/seed.py` — watchlist + concept→XBRL-tag aliases
- `stance/ingest/`, `stance/retrieval/`, `stance/numeric/`, `stance/agents/` —
  filled in phase by phase, see `KAGGLE_BUILD_PLAN.md`

Notebooks in `notebooks/` are thin drivers that call into `stance/` — they
contain no logic of their own, which is what lets this port to GCP later
without a rewrite.
