"""Settings — local-only: reads from a .env file in the repo root, with
sensible defaults matching docker-compose.yml so a fresh clone works with
zero configuration beyond `docker compose up -d` and API keys.
"""
from __future__ import annotations

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Matches docker-compose.yml's postgres service by default.
    database_url: str = "postgresql+psycopg://stance:stance@localhost:5432/stance"

    groq_api_key: str = ""
    google_ai_api_key: str = ""
    deepseek_api_key: str = ""

    # EDGAR requires a descriptive User-Agent with a real contact email,
    # and enforces a 10 req/s ceiling. Override via .env for your own use.
    sec_user_agent: str = "STANCE-MTech-Project research@example.com"
    edgar_rate_limit_per_sec: float = 8.0  # stay under the 10/s ceiling with margin

    embed_model_name: str = "BAAI/bge-small-en-v1.5"
    embed_dim: int = 384
    reranker_model_name: str = "BAAI/bge-reranker-base"


settings = Settings()

# LiteLLM auto-detects each provider's key from a provider-specific env var
# (GROQ_API_KEY, DEEPSEEK_API_KEY, GEMINI_API_KEY, ...) based on the
# "<provider>/<model>" prefix in NODE_POLICY — it must NOT be set globally
# via litellm.api_key, which would apply one key to every provider's calls.
# GROQ_API_KEY and DEEPSEEK_API_KEY already match LiteLLM's expected names;
# only Gemini's needs bridging, since we keep the .env name GOOGLE_AI_API_KEY
# for clarity but LiteLLM looks for GEMINI_API_KEY.
if settings.google_ai_api_key:
    os.environ.setdefault("GEMINI_API_KEY", settings.google_ai_api_key)
if settings.groq_api_key:
    os.environ.setdefault("GROQ_API_KEY", settings.groq_api_key)
if settings.deepseek_api_key:
    os.environ.setdefault("DEEPSEEK_API_KEY", settings.deepseek_api_key)
