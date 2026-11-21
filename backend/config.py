"""Runtime settings, read once from the environment.

Secrets (the master key, the operator's LLM key) are kept as `SecretStr` so they
never show up in reprs or logs (AGENTS.md rule 9).
"""

import os
from functools import lru_cache
from typing import TYPE_CHECKING

from pydantic import BaseModel, SecretStr

if TYPE_CHECKING:
    from qdrant_client import AsyncQdrantClient


class Settings(BaseModel, frozen=True):
    database_url: str
    qdrant_url: str
    qdrant_api_key: SecretStr | None = None  # Qdrant Cloud; empty for a local Qdrant
    ollama_url: str
    local_model: str
    master_key: SecretStr | None
    operator_llm_provider: str | None
    operator_llm_key: SecretStr | None
    operator_llm_model: str | None
    memory_dir: str
    registry_dir: str
    whisper_model: str = "base.en"
    low_memory: bool = False  # hosted 512 MB profile; local development keeps every model
    demo: bool = True  # the "Demo" button: anyone who can reach the API may sign in as Alex
    # Who gets the built-in course: "demo" (the demo person and classmates) or "all" accounts.
    built_in_course: str = "demo"


def _optional(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def _optional_secret(name: str) -> SecretStr | None:
    value = _optional(name)
    return SecretStr(value) if value else None


@lru_cache
def get_settings() -> Settings:
    # A single Gemini key is enough for the hosted demo. Explicit operator settings win;
    # a different provider's key must never be paired with Gemini by accident.
    gemini_key = _optional_secret("GEMINI_API_KEY")
    operator_provider = _optional("LODESTAR_OPERATOR_LLM_PROVIDER")
    operator_key = _optional_secret("LODESTAR_OPERATOR_LLM_KEY")
    operator_model = _optional("LODESTAR_OPERATOR_LLM_MODEL")
    if gemini_key and operator_provider in (None, "gemini") and operator_key is None:
        operator_provider = "gemini"
        operator_key = gemini_key
        operator_model = operator_model or "gemini-3.5-flash-lite"
    return Settings(
        database_url=os.environ.get(
            "DATABASE_URL", "postgresql://lodestar:lodestar@localhost:5442/lodestar"
        ),
        qdrant_url=os.environ.get("QDRANT_URL", "http://localhost:6333"),
        qdrant_api_key=_optional_secret("QDRANT_API_KEY"),
        ollama_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
        local_model=os.environ.get("LODESTAR_LOCAL_MODEL", "qwen3.5:4b"),
        master_key=_optional_secret("LODESTAR_MASTER_KEY"),
        operator_llm_provider=operator_provider,
        operator_llm_key=operator_key,
        operator_llm_model=operator_model,
        memory_dir=os.environ.get("LODESTAR_MEMORY_DIR", "memory"),
        registry_dir=os.environ.get("LODESTAR_REGISTRY_DIR", "registry"),
        whisper_model=os.environ.get("LODESTAR_WHISPER_MODEL", "base.en"),
        low_memory=os.environ.get("LODESTAR_LOW_MEMORY", "0") == "1",
        demo=os.environ.get("LODESTAR_DEMO", "1") != "0",
        built_in_course=os.environ.get("LODESTAR_BUILT_IN_COURSE", "demo").strip() or "demo",
    )


def qdrant_client(settings: Settings, timeout: int = 5) -> AsyncQdrantClient:
    """The Qdrant client: a local server, or Qdrant Cloud when QDRANT_API_KEY is set."""
    from qdrant_client import AsyncQdrantClient

    key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
    return AsyncQdrantClient(url=settings.qdrant_url, api_key=key, timeout=timeout)
