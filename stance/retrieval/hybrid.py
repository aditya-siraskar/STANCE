"""Hybrid retrieval: dense (pgvector cosine) + lexical (Postgres full-text
search), fused with reciprocal-rank fusion, in one SQL query. Both legs
share the same metadata prefilter (cik / fiscal_year / item_code) — this
is what makes "what are their risks" retrieve only from Item 1A.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

_RRF_K = 60  # standard RRF damping constant

_HYBRID_SQL = """
WITH dense AS (
    SELECT chunk_id, RANK() OVER (ORDER BY embedding <=> :query_embedding) AS rnk
    FROM chunks
    WHERE (:cik IS NULL OR cik = :cik)
      AND (:fiscal_year IS NULL OR fiscal_year = :fiscal_year)
      AND (:item_code IS NULL OR item_code = :item_code)
    ORDER BY embedding <=> :query_embedding
    LIMIT :candidate_pool
),
lexical AS (
    SELECT chunk_id, RANK() OVER (ORDER BY ts_rank_cd(tsv, query) DESC) AS rnk
    FROM chunks, plainto_tsquery('english', :query_text) query
    WHERE tsv @@ query
      AND (:cik IS NULL OR cik = :cik)
      AND (:fiscal_year IS NULL OR fiscal_year = :fiscal_year)
      AND (:item_code IS NULL OR item_code = :item_code)
    ORDER BY ts_rank_cd(tsv, query) DESC
    LIMIT :candidate_pool
),
fused AS (
    SELECT
        COALESCE(dense.chunk_id, lexical.chunk_id) AS chunk_id,
        COALESCE(1.0 / (:rrf_k + dense.rnk), 0) + COALESCE(1.0 / (:rrf_k + lexical.rnk), 0) AS score
    FROM dense
    FULL OUTER JOIN lexical ON dense.chunk_id = lexical.chunk_id
)
SELECT c.chunk_id, c.text, c.accession_no, c.cik, c.ticker, c.fiscal_year, c.item_code,
       c.parent_chunk_id, c.section_id, fused.score
FROM fused
JOIN chunks c ON c.chunk_id = fused.chunk_id
ORDER BY fused.score DESC
LIMIT :top_k
"""


def hybrid_search(
    engine: Engine,
    query_text: str,
    query_embedding: list[float],
    *,
    cik: str | None = None,
    fiscal_year: int | None = None,
    item_code: str | None = None,
    candidate_pool: int = 50,
    top_k: int = 8,
) -> list[dict]:
    """Returns up to top_k chunks ranked by RRF-fused dense+lexical score,
    each scoped by the given metadata prefilter."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(_HYBRID_SQL),
            {
                "query_text": query_text,
                "query_embedding": str(query_embedding),
                "cik": cik,
                "fiscal_year": fiscal_year,
                "item_code": item_code,
                "candidate_pool": candidate_pool,
                "top_k": top_k,
                "rrf_k": _RRF_K,
            },
        ).mappings().all()
    return [dict(r) for r in rows]
