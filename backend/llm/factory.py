"""The one door to LLMs (docs/plan/03, "LLM providers" and the reliability ladder).

`generate` walks the ladder: the user's hosted provider (with their key) -> local Ollama ->
`NoModelAvailable`, at which point the caller uses a fixed template. Every step down is reported
in `degraded`. Keys are decrypted here, in memory, for one call; they never leave this module.
"""

import asyncio
import base64
import json
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, TypeVar
from uuid import UUID

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.config import Settings
from backend.contracts.llm import LlmSelection
from backend.db import tables as t
from backend.db.consent_store import granted_switches
from backend.db.llm_store import (
    get_credential,
    save_credential,
    set_credential_status,
    set_selection,
)
from backend.llm.deidentify import scrub_messages
from backend.llm.providers import build_chat_model, list_models
from backend.llm.stub import Responder, StubChatModel
from backend.llm.vault import Vault
from backend.registry.models import Registry

log = logging.getLogger(__name__)

# An interactive call that takes longer than this falls to the next rung (Ollama, then a template).
CALL_TIMEOUT_S = 30.0

M = TypeVar("M", bound=BaseModel)


class NoModelAvailable(RuntimeError):
    def __init__(self, degraded: Sequence[str]) -> None:
        super().__init__("no LLM available; use a template")
        self.degraded = list(degraded)


@dataclass(frozen=True)
class LlmReply:
    text: str
    provider: str
    model: str
    degraded: tuple[str, ...]


@dataclass(frozen=True)
class StructuredReply[T]:
    value: T
    provider: str
    model: str
    degraded: tuple[str, ...]


@dataclass(frozen=True)
class _Rung:
    provider: str
    model: str
    chat: BaseChatModel
    # Hosted rungs only see de-identified text: the user's name is replaced (docs/plan/14).
    hide_names: tuple[str, ...] | None = None
    operator: bool = False  # the server's key, not the student's: its errors aren't theirs

    def outbound(self, messages: Sequence[BaseMessage]) -> list[BaseMessage]:
        if self.hide_names is None:
            return list(messages)
        return scrub_messages(messages, self.hide_names)


def _status_for(exc: BaseException) -> str | None:
    """Map a provider error to a credential status, when it's about the key."""
    code = getattr(exc, "status_code", None) or getattr(
        getattr(exc, "response", None), "status_code", None
    )
    name = type(exc).__name__
    if code in (401, 403) or "Authentication" in name or "PermissionDenied" in name:
        return "rejected"
    if code == 402:
        return "out_of_credit"
    return None


class LlmFactory:
    def __init__(
        self,
        registry: Registry,
        settings: Settings,
        engine: AsyncEngine,
        *,
        base_overrides: dict[str, str] | None = None,
        stub_responder: Responder | None = None,
        call_timeout_s: float = CALL_TIMEOUT_S,
    ) -> None:
        self.call_timeout_s = call_timeout_s
        self.registry = registry
        self.settings = settings
        self.engine = engine
        self.vault = Vault(settings.master_key.get_secret_value() if settings.master_key else None)
        self.base_overrides = base_overrides or {}
        self.stub_responder = stub_responder

    def base_for(self, provider_id: str) -> str | None:
        if provider_id in self.base_overrides:
            return self.base_overrides[provider_id]
        if provider_id == "ollama":
            return self.settings.ollama_url
        return None

    def api_base(self, provider_id: str) -> str:
        """Root used for model listing; overrides win (tests)."""
        override = self.base_overrides.get(provider_id)
        if override:
            return override
        if provider_id == "ollama":
            return self.settings.ollama_url
        base = self.registry.provider(provider_id).api_base
        if base is None:
            raise ValueError(f"{provider_id} has no api_base")
        return str(base)

    def _stub(self) -> _Rung:
        chat = (
            StubChatModel(responder=self.stub_responder) if self.stub_responder else StubChatModel()
        )
        return _Rung("stub", "stub", chat)

    def _local(self) -> _Rung:
        provider = self.registry.provider("ollama")
        chat = build_chat_model(provider, self.settings.local_model, None, self.base_for("ollama"))
        return _Rung("ollama", self.settings.local_model, chat)

    async def _ladder(self, user_id: UUID, selection: LlmSelection) -> list[_Rung]:
        if selection.mode == "stub":
            return [self._stub()]
        rungs: list[_Rung] = []
        if selection.mode == "hosted" and self.vault.available:
            async with self.engine.connect() as conn:
                stored = await get_credential(conn, user_id, selection.provider)
            if stored is not None and stored.status != "rejected":
                key = self.vault.open(user_id, selection.provider, stored.ciphertext, stored.nonce)
                provider = self.registry.provider(selection.provider)
                chat = build_chat_model(provider, selection.model, key, self.base_for(provider.id))
                async with self.engine.connect() as conn:
                    name = (
                        await conn.execute(
                            select(t.users.c.display_name).where(t.users.c.user_id == user_id)
                        )
                    ).scalar_one_or_none()
                hide = (name,) if name else ()
                rungs.append(_Rung(provider.id, selection.model, chat, hide_names=hide))
        if (operator := await self._operator(user_id)) is not None:
            rungs.append(operator)
        rungs.append(self._local())
        return rungs

    async def _operator(self, user_id: UUID) -> _Rung | None:
        """The server's own hosted model (LODESTAR_OPERATOR_LLM_*), for a deployment without
        Ollama, such as Render. It is a cloud model, so it only runs for students who switched
        Cloud AI on (docs/plan/14), and their name is hidden from it as with their own key."""
        s = self.settings
        if not (s.operator_llm_provider and s.operator_llm_key and s.operator_llm_model):
            return None
        async with self.engine.connect() as conn:
            consent = await granted_switches(conn, user_id, self.registry.consent)
            name = (
                await conn.execute(
                    select(t.users.c.display_name).where(t.users.c.user_id == user_id)
                )
            ).scalar_one_or_none()
        if "cloud_ai" not in consent:
            return None
        provider = self.registry.provider(s.operator_llm_provider)
        key = s.operator_llm_key.get_secret_value()
        chat = build_chat_model(provider, s.operator_llm_model, key, self.base_for(provider.id))
        hide = (name,) if name else ()
        return _Rung(provider.id, s.operator_llm_model, chat, hide_names=hide, operator=True)

    async def _walk(
        self, user_id: UUID, selection: LlmSelection, call: Any
    ) -> tuple[Any, _Rung, tuple[str, ...]]:
        rungs = await self._ladder(user_id, selection)
        first = selection.provider if selection.mode != "local" else "ollama"
        degraded: list[str] = []
        if selection.mode == "hosted" and rungs[0].provider != selection.provider:
            degraded.append(f"llm:{selection.provider}->{rungs[0].provider}")
        for rung in rungs:
            try:
                result = await asyncio.wait_for(call(rung), self.call_timeout_s)
                return result, rung, tuple(degraded)
            except Exception as exc:
                log.warning("LLM call failed on %s: %s", rung.provider, type(exc).__name__)
                status = _status_for(exc)
                if status and rung.provider not in ("ollama", "stub") and not rung.operator:
                    async with self.engine.begin() as conn:
                        await set_credential_status(conn, user_id, rung.provider, status)
                nxt = rungs[rungs.index(rung) + 1].provider if rung is not rungs[-1] else "template"
                step = f"llm:{rung.provider}->{nxt}"
                if step not in degraded:
                    degraded.append(step)
        if not degraded:
            degraded.append(f"llm:{first}->template")
        raise NoModelAvailable(degraded)

    async def generate(
        self, user_id: UUID, selection: LlmSelection, messages: Sequence[BaseMessage]
    ) -> LlmReply:
        async def call(rung: _Rung) -> str:
            reply = await rung.chat.ainvoke(rung.outbound(messages))
            return reply.text if hasattr(reply, "text") else str(reply.content)

        text, rung, degraded = await self._walk(user_id, selection, call)
        return LlmReply(text, rung.provider, rung.model, degraded)

    async def gemini_pdf_page(self, user_id: UUID, data: bytes, prompt: str, schema: type[M]) -> M:
        """OCR has no text-only/local fallback. The key stays inside this factory.

        Native PDF vision retains handwritten formulas and layout. Source pages are sent
        only with Cloud AI enabled; provider errors never expose request headers or bodies.
        """
        async with self.engine.connect() as conn:
            consent = await granted_switches(conn, user_id, self.registry.consent)
            stored = await get_credential(conn, user_id, "gemini")
        if "cloud_ai" not in consent:
            raise ValueError("Enable Cloud AI in Settings to read scanned pages with Gemini.")
        if stored is not None and stored.status != "rejected" and self.vault.available:
            key = self.vault.open(user_id, "gemini", stored.ciphertext, stored.nonce)
        elif self.settings.operator_llm_provider == "gemini" and self.settings.operator_llm_key:
            key = self.settings.operator_llm_key.get_secret_value()
        else:
            raise ValueError("Add your Gemini key in Settings to read scanned pages.")
        model = "gemini-3.5-flash-lite"
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "application/pdf",
                                "data": base64.b64encode(data).decode("ascii"),
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseJsonSchema": schema.model_json_schema(),
            },
        }
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                for attempt in range(3):
                    response = await client.post(
                        f"{self.api_base('gemini')}/models/{model}:generateContent",
                        headers={"x-goog-api-key": key},
                        json=body,
                    )
                    if response.status_code not in (429, 500, 502, 503, 504) or attempt == 2:
                        break
                    delay = 2**attempt
                    if response.status_code == 429:
                        try:
                            delay = min(45, max(10, int(response.headers.get("Retry-After", "30"))))
                        except ValueError:
                            delay = 30
                    await asyncio.sleep(delay)
            if response.status_code in (401, 403):
                raise ValueError("Gemini could not authorise OCR. Check your key in Settings.")
            if response.status_code == 404:
                raise ValueError(
                    "Gemini 3.5 Flash Lite is unavailable for this key. Check Settings."
                )
            if response.status_code == 429:
                raise ValueError("Gemini's OCR limit was reached. Try again later.")
            response.raise_for_status()
            candidate = response.json()["candidates"][0]
            if candidate.get("finishReason") != "STOP":
                raise ValueError("Gemini did not finish reading this page. Try a smaller file.")
            text = "".join(p.get("text", "") for p in candidate["content"]["parts"])
            return schema.model_validate_json(text)
        except (
            httpx.HTTPError,
            KeyError,
            IndexError,
            TypeError,
            AttributeError,
            json.JSONDecodeError,
            ValidationError,
        ):
            raise ValueError("Gemini could not read this page. Try again later.") from None

    async def import_gemini_environment(self, user_id: UUID) -> list[str]:
        """Explicit local setup command: seal the supplied environment key for one user."""
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise ValueError("GEMINI_API_KEY is not configured.")
        async with httpx.AsyncClient(timeout=30) as client:
            models = await list_models(
                self.registry.provider("gemini"), key, self.api_base("gemini"), client
            )
        model = "gemini-3.5-flash-lite"
        if model not in models:
            return models
        sealed = self.vault.seal(user_id, "gemini", key)
        async with self.engine.begin() as conn:
            await save_credential(conn, user_id, "gemini", sealed, "ok")
            await set_selection(
                conn, user_id, LlmSelection(mode="hosted", provider="gemini", model=model)
            )
        return models

    async def structured(
        self,
        user_id: UUID,
        selection: LlmSelection,
        messages: Sequence[BaseMessage],
        schema: type[M],
    ) -> StructuredReply[M]:
        async def call(rung: _Rung) -> M:
            if rung.provider == "stub":
                reply = await rung.chat.ainvoke(list(messages))
                return schema.model_validate_json(str(reply.content))
            caps = self.registry.provider(rung.provider).capabilities
            method = caps.structured_method
            runnable = rung.chat.with_structured_output(schema, method=method)
            value = await runnable.ainvoke(rung.outbound(messages))
            return value if isinstance(value, schema) else schema.model_validate(value)

        value, rung, degraded = await self._walk(user_id, selection, call)
        return StructuredReply(value, rung.provider, rung.model, degraded)
