"""Cross-encoder reranking: bge-reranker-base over the top ~15-50 hybrid
candidates, keeping the top ~5-8. Requires the `retrieval` extra.
"""
from __future__ import annotations

from functools import lru_cache

from stance.config import settings


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import CrossEncoder  # deferred import

    return CrossEncoder(settings.reranker_model_name)


def rerank(query: str, candidates: list[dict], top_k: int = 8) -> list[dict]:
    """candidates: chunk rows with a 'text' field, as returned by
    hybrid_search. Returns the top_k re-scored, in descending order,
    each annotated with a 'rerank_score'."""
    if not candidates:
        return []
    model = _get_model()
    pairs = [(query, c["text"]) for c in candidates]
    scores = model.predict(pairs)
    scored = [dict(c, rerank_score=float(s)) for c, s in zip(candidates, scores)]
    scored.sort(key=lambda c: c["rerank_score"], reverse=True)
    return scored[:top_k]
