"""Demo sign-in keeps one preparation task running across short polling requests."""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import httpx

from backend.api import demo
from backend.api.main import create_app
from backend.contracts.views import CreatedUser


async def test_demo_preparation_does_not_timeout_or_start_duplicate_seeds(monkeypatch):
    ready = asyncio.Event()
    calls = 0
    user = CreatedUser(user_id=uuid4(), token="test-demo-token")

    async def seed(_):
        nonlocal calls
        calls += 1
        await ready.wait()
        return user, False

    monkeypatch.setattr(demo, "run_in_threadpool", seed)
    monkeypatch.setattr(demo, "get_settings", lambda: SimpleNamespace(demo=True))
    app = create_app(with_lifespan=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = await client.post("/demo")
        assert first.status_code == 202 and first.json() == {"status": "preparing"}
        assert (await client.post("/demo")).status_code == 202
        assert calls == 1
        ready.set()
        result = await client.post("/demo")
        assert result.status_code == 200 and result.json()["token"] == user.token
        assert calls == 1
