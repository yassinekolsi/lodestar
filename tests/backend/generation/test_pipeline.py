"""Exercise the retained content pipeline with an isolated arithmetic generator.

The shipped course serves curated questions, so GENERATORS is deliberately empty. These tests
inject a fixture for the reusable pipeline rather than depend on removed game implementations.
"""

import json
import random
from collections import Counter
from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from langchain_core.messages import BaseMessage
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from backend.contracts.common import Contract
from backend.contracts.llm import LlmSelection
from backend.db.engine import sync_url
from backend.db.twin_store import create_user
from backend.generation.generators.base import TextRequest
from backend.generation.generators.registry import GENERATORS
from backend.generation.pipeline import ContentService
from backend.llm.factory import LlmFactory
from backend.registry.loader import load_registry
from tests.backend.agent.conftest import test_settings as settings_for_tests

REGISTRY = load_registry()
STUB = LlmSelection(mode="stub", provider="stub", model="stub")
GAME = "quiz_notes"


class Arithmetic(Contract):
    a: int
    b: int
    total: int
    phrase: str


class Draft(Contract):
    total: int
    phrase: str


class FixtureGenerator:
    game_id = GAME
    schema = Arithmetic

    def build(self, knobs, rng, theme):
        a, b = rng.randrange(100000), rng.randrange(100000)
        return Arithmetic(a=a, b=b, total=a + b, phrase="Add the two values.")

    def text_request(self, content):
        return TextRequest("fixture", {"data": content.model_dump()}, Draft)

    def apply_text(self, content: Contract, text: BaseModel):
        return content.model_copy(update=text.model_dump())

    def check(self, content, knobs):
        return [] if content.total == content.a + content.b else ["The sum is incorrect."]

    def signature(self, content):
        return f"{content.a}+{content.b}={content.total}"


@pytest.fixture(autouse=True)
def isolated_generator(monkeypatch):
    monkeypatch.setitem(GENERATORS, GAME, FixtureGenerator())
    monkeypatch.setattr("backend.generation.pipeline.load_prompt", lambda _: ("1", "{data}"))


def fuzzing_responder(seed: int):
    rng = random.Random(seed)

    def respond(messages: Sequence[BaseMessage]) -> str:
        original = json.loads(str(messages[1].content))
        roll = rng.random()
        if roll < 0.15:
            return "not json at all"
        if roll < 0.55:
            return json.dumps({"total": original["total"] + 1, "phrase": "Add the values."})
        if roll < 0.75:
            return json.dumps({"total": original["total"], "phrase": "My diagnosis says add."})
        return json.dumps({"total": original["total"], "phrase": "Combine both values."})

    return respond


@pytest.fixture
async def aengine(db_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(sync_url(db_url))
    yield engine
    await engine.dispose()


async def _user(engine: AsyncEngine) -> UUID:
    async with engine.begin() as conn:
        user_id, _ = await create_user(conn)
    return user_id


async def test_500_fuzzed_generations_never_serve_invalid_content(aengine: AsyncEngine) -> None:
    llm = LlmFactory(REGISTRY, settings_for_tests(), aengine, stub_responder=fuzzing_responder(7))
    service = ContentService(aengine, llm, live_llm="always")
    user = await _user(aengine)
    sources: Counter[str] = Counter()
    for i in range(500):
        prepared = await service.prepare(
            user_id=user, selection=STUB, game_id=GAME, level=0.5, knobs={}, seed=i
        )
        assert prepared is not None
        gen = GENERATORS[GAME]
        content = gen.schema.model_validate(prepared.content)
        assert await service.validate(gen, content, {}, None) == [], prepared.source
        sources[prepared.source] += 1
    assert sources["generated"] > 50 and sources["code"] > 50


async def test_pool_fill_and_take_never_repeats_for_a_user(aengine: AsyncEngine) -> None:
    service = ContentService(aengine, llm=None)
    assert await service.fill_pool(GAME, per_level=2, levels=(0.5,), seed=99) == 2
    assert await service.fill_pool(GAME, per_level=2, levels=(0.5,)) == 0
    alice, bob = await _user(aengine), await _user(aengine)
    first = await service.take_from_pool(alice, GAME, 0.5)
    second = await service.take_from_pool(alice, GAME, 0.5)
    assert first and second and first.item_id != second.item_id
    assert await service.take_from_pool(alice, GAME, 0.5) is None
    assert await service.take_from_pool(bob, GAME, 0.5) is not None


async def test_without_any_llm_play_still_gets_valid_content(aengine: AsyncEngine) -> None:
    service = ContentService(aengine, llm=None)
    user = await _user(aengine)
    prepared = await service.prepare(
        user_id=user, selection=STUB, game_id=GAME, level=0.5, knobs={}, seed=1
    )
    assert prepared is not None and prepared.source in ("code", "pool")
    assert not ContentService.needs_content("quiz_conditional")
    assert (
        await service.prepare(
            user_id=user, selection=STUB, game_id="quiz_conditional", level=0.5, knobs={}, seed=1
        )
        is None
    )


async def test_novelty_rejects_what_this_user_just_saw(aengine: AsyncEngine) -> None:
    seen: set[tuple[UUID, str, str]] = set()

    async def similarity(user: UUID, game: str, signature: str, since: datetime):
        return float((user, game, signature) in seen)

    async def record(user, game, level, item_id, signature):
        seen.add((user, game, signature))

    memory = SimpleNamespace(max_similarity_served=similarity, record_served=record)
    service = ContentService(aengine, llm=None, memory=memory)
    user = await _user(aengine)
    first = await service.prepare(
        user_id=user, selection=STUB, game_id=GAME, level=0.8, knobs={}, seed=5
    )
    again = await service.prepare(
        user_id=user, selection=STUB, game_id=GAME, level=0.8, knobs={}, seed=5
    )
    assert first and again and first.content != again.content
    assert "code_retries" in again.report
    other = await service.prepare(
        user_id=await _user(aengine), selection=STUB, game_id=GAME, level=0.8, knobs={}, seed=5
    )
    assert other and other.content == first.content


@pytest.mark.skipif(
    not __import__("os").environ.get("LODESTAR_OLLAMA_TESTS"),
    reason="needs local Ollama; set LODESTAR_OLLAMA_TESTS=1",
)
async def test_local_ollama_generations_are_valid_or_fall_back(aengine: AsyncEngine) -> None:
    import os

    settings = settings_for_tests(ollama_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    service = ContentService(aengine, LlmFactory(REGISTRY, settings, aengine), live_llm="always")
    local = LlmSelection(mode="local", provider="ollama", model=settings.local_model)
    user = await _user(aengine)
    for i in range(8):
        prepared = await service.prepare(
            user_id=user, selection=local, game_id=GAME, level=0.4, knobs={}, seed=i
        )
        assert prepared is not None
        gen = GENERATORS[GAME]
        assert (
            await service.validate(gen, gen.schema.model_validate(prepared.content), {}, None) == []
        )
