"""Embedding: bge-small-en-v1.5, 384-dim, CPU. Requires the `retrieval`
extra (`pip install -e ".[retrieval]"`) — kept out of core so contract/
numeric/parsing tests never need to pull torch.
"""
from __future__ import annotations

from functools import lru_cache

from stance.config import settings


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer  # deferred import

    return SentenceTransformer(settings.embed_model_name)


def embed_texts(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """Returns one 384-dim embedding vector per input text, in order."""
    model = _get_model()
    vectors = model.encode(texts, batch_size=batch_size, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
