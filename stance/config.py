"""Settings — reads from Kaggle Secrets when running in a Kaggle notebook,
falling back to environment variables / a local .env otherwise. One class,
two sources, so notebook code and local/CI code are identical.
"""
from __future__ import annotations

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_kaggle_secrets() -> dict[str, str]:
    """Best-effort load of Kaggle Secrets into the process environment.

    No-op outside Kaggle (import fails silently) or if a secret is missing
    (secret is simply left unset — callers fail with a clear "not configured"
    error rather than a silent None propagating deep into the stack).
    """
    try:
        from kaggle_secrets import UserSecretsClient  # type: ignore
    except ImportError:
        return {}

    client = UserSecretsClient()
    loaded: dict[str, str] = {}
    for key in ("NEON_DATABASE_URL", "GROQ_API_KEY", "GOOGLE_AI_API_KEY", "SEC_USER_AGENT"):
        try:
            value = client.get_secret(key)
        except Exception:  # noqa: BLE001, S112 — an unset secret must not crash config import
            continue
        os.environ.setdefault(key, value)
        loaded[key] = value
    return loaded


_load_kaggle_secrets()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    neon_database_url: str = ""
    groq_api_key: str = ""
    google_ai_api_key: str = ""

    # EDGAR requires a descriptive User-Agent with a real contact email,
    # and enforces a 10 req/s ceiling. Override via env/secret for your own use.
    sec_user_agent: str = "STANCE-MTech-Project research@example.com"
    edgar_rate_limit_per_sec: float = 8.0  # stay under the 10/s ceiling with margin

    embed_model_name: str = "BAAI/bge-small-en-v1.5"
    embed_dim: int = 384
    reranker_model_name: str = "BAAI/bge-reranker-base"


settings = Settings()
