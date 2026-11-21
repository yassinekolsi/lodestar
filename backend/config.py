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
    demo: bool = True  # the "Demo" button: anyone who can reach the API may sign in as Alex


def _optional(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def _optional_secret(name: str) -> SecretStr | None:
    value = _optional(name)
    return SecretStr(value) if value else None


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.environ.get(
            "DATABASE_URL", "postgresql://lodestar:lodestar@localhost:5442/lodestar"
        ),
        qdrant_url=os.environ.get("QDRANT_URL", "http://localhost:6333"),
        qdrant_api_key=_optional_secret("QDRANT_API_KEY"),
        ollama_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
        local_model=os.environ.get("LODESTAR_LOCAL_MODEL", "qwen3.5:4b"),
        master_key=_optional_secret("LODESTAR_MASTER_KEY"),
        operator_llm_provider=_optional("LODESTAR_OPERATOR_LLM_PROVIDER"),
        operator_llm_key=_optional_secret("LODESTAR_OPERATOR_LLM_KEY"),
        operator_llm_model=_optional("LODESTAR_OPERATOR_LLM_MODEL"),
        memory_dir=os.environ.get("LODESTAR_MEMORY_DIR", "memory"),
        registry_dir=os.environ.get("LODESTAR_REGISTRY_DIR", "registry"),
        whisper_model=os.environ.get("LODESTAR_WHISPER_MODEL", "base.en"),
        demo=os.environ.get("LODESTAR_DEMO", "1") != "0",
    )


def qdrant_client(settings: Settings, timeout: int = 5) -> AsyncQdrantClient:
    """The Qdrant client: a local server, or Qdrant Cloud when QDRANT_API_KEY is set."""
    from qdrant_client import AsyncQdrantClient

    key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
    return AsyncQdrantClient(url=settings.qdrant_url, api_key=key, timeout=timeout)
