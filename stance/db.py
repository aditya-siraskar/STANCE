"""Neon Postgres engine + schema. One database, two destinations:
chunk vectors (pgvector) and XBRL facts (relational) — a citation joining
to a computed figure is a SQL join, not a distributed lookup.

Schema creation is idempotent (`IF NOT EXISTS` throughout) so re-running
00_setup_and_schema.ipynb never fails or duplicates.
"""
from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from stance.config import settings

_SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS companies (
    cik         TEXT PRIMARY KEY,
    ticker      TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    sic         TEXT
);

CREATE TABLE IF NOT EXISTS filings (
    accession_no    TEXT PRIMARY KEY,
    cik             TEXT NOT NULL REFERENCES companies(cik),
    form_type       TEXT NOT NULL,
    fiscal_year     INTEGER NOT NULL,
    fiscal_period   TEXT NOT NULL DEFAULT 'FY',
    filing_date     DATE,
    primary_doc_url TEXT,
    parser_version  TEXT,
    ingest_status   TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS sections (
    section_id   TEXT PRIMARY KEY,
    accession_no TEXT NOT NULL REFERENCES filings(accession_no),
    item_code    TEXT NOT NULL,
    title        TEXT,
    text         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id         TEXT PRIMARY KEY,
    section_id       TEXT NOT NULL REFERENCES sections(section_id),
    parent_chunk_id  TEXT,
    accession_no     TEXT NOT NULL,
    cik              TEXT NOT NULL,
    ticker           TEXT NOT NULL,
    fiscal_year      INTEGER NOT NULL,
    item_code        TEXT NOT NULL,
    text             TEXT NOT NULL,
    embedding        vector(384),
    tsv              tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    embed_model      TEXT,
    chunker_version  TEXT
);

CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_scope_idx ON chunks (cik, fiscal_year, item_code);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS xbrl_facts (
    fact_id       TEXT PRIMARY KEY,
    accession_no  TEXT NOT NULL REFERENCES filings(accession_no),
    cik           TEXT NOT NULL,
    element_name  TEXT NOT NULL,
    label         TEXT,
    value         NUMERIC NOT NULL,
    unit          TEXT NOT NULL,
    period_type   TEXT NOT NULL,   -- 'instant' | 'duration'
    period_start  DATE,
    period_end    DATE,
    fiscal_year   INTEGER NOT NULL,
    fiscal_period TEXT NOT NULL DEFAULT 'FY',
    segment_axis  JSONB,
    source_url    TEXT
);

CREATE INDEX IF NOT EXISTS xbrl_facts_lookup_idx
    ON xbrl_facts (cik, element_name, fiscal_year, fiscal_period)
    WHERE segment_axis IS NULL;

CREATE TABLE IF NOT EXISTS fact_aliases (
    concept       TEXT NOT NULL,
    element_name  TEXT NOT NULL,
    cik           TEXT,            -- NULL = applies to any company
    priority      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (concept, element_name, cik)
);

CREATE TABLE IF NOT EXISTS query_traces (
    trace_id            TEXT PRIMARY KEY,
    question             TEXT NOT NULL,
    plan                 JSONB,
    route                TEXT,
    retrieved_chunk_ids   JSONB,
    computation_specs     JSONB,
    verifier_report       JSONB,
    created_at            TIMESTAMPTZ DEFAULT now()
);
"""


def get_engine() -> Engine:
    if not settings.neon_database_url:
        raise RuntimeError(
            "NEON_DATABASE_URL is not set. Add it as a Kaggle Secret or in .env."
        )
    return create_engine(settings.neon_database_url, pool_pre_ping=True)


def init_schema(engine: Engine | None = None) -> None:
    """Create all tables/indexes/extensions. Safe to run repeatedly."""
    engine = engine or get_engine()
    with engine.begin() as conn:
        for statement in _SCHEMA_SQL.strip().split(";\n\n"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
