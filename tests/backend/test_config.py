"""Hosted Gemini configuration uses the documented environment variable without exposing keys."""

import pytest

from backend.config import get_settings


@pytest.fixture(autouse=True)
def clean_provider_environment(monkeypatch: pytest.MonkeyPatch):
    for name in (
        "GEMINI_API_KEY",
        "LODESTAR_OPERATOR_LLM_PROVIDER",
        "LODESTAR_OPERATOR_LLM_KEY",
        "LODESTAR_OPERATOR_LLM_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_gemini_key_alone_enables_hosted_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-config-canary-1234")
    settings = get_settings()
    assert settings.operator_llm_provider == "gemini"
    assert settings.operator_llm_model == "gemini-3.5-flash-lite"
    assert settings.operator_llm_key.get_secret_value() == "gemini-config-canary-1234"
    assert "gemini-config-canary" not in repr(settings)


@pytest.mark.parametrize("provider", ["gemini", "openai"])
def test_explicit_operator_settings_win(monkeypatch: pytest.MonkeyPatch, provider: str) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-config-canary-1234")
    monkeypatch.setenv("LODESTAR_OPERATOR_LLM_PROVIDER", provider)
    monkeypatch.setenv("LODESTAR_OPERATOR_LLM_KEY", "explicit-canary-1234")
    monkeypatch.setenv("LODESTAR_OPERATOR_LLM_MODEL", "configured-model")
    settings = get_settings()
    assert settings.operator_llm_provider == provider
    assert settings.operator_llm_model == "configured-model"
    assert settings.operator_llm_key.get_secret_value() == "explicit-canary-1234"


def test_gemini_key_cannot_be_used_as_another_providers_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-config-canary-1234")
    monkeypatch.setenv("LODESTAR_OPERATOR_LLM_PROVIDER", "openai")
    assert get_settings().operator_llm_key is None
