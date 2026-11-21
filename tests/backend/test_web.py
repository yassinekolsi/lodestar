"""The hosted server (backend/api/web.py): the API under /api, the built frontend everywhere else,
one lifespan, and WebSockets on the same origin."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from backend import i18n
from backend.api.web import create_web


def _api(started: list[str]) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        started.append("up")
        yield
        started.append("down")

    api = FastAPI(lifespan=lifespan)
    api.add_middleware(i18n.LocaleMiddleware)

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "locale": i18n.current()}

    @api.websocket("/sessions/stream")
    async def stream(socket: WebSocket) -> None:
        await socket.accept()
        await socket.send_text(f"hello {i18n.current()}")
        await socket.close()

    return api


def test_api_static_files_and_page_fallback(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<!doctype html><title>Lodestar</title>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    started: list[str] = []
    with TestClient(create_web(_api(started), tmp_path)) as client:
        assert started == ["up"]  # the API's lifespan runs once, through the wrapper
        assert client.get("/api/health").json() == {"status": "ok", "locale": "en"}
        assert client.get("/api/health", headers={"X-Lodestar-Locale": "fr"}).json() == {
            "status": "ok",
            "locale": "fr",
        }
        assert client.get("/assets/app.js").text == "console.log(1)"
        assert "Lodestar" in client.get("/").text
        assert "Lodestar" in client.get("/some/page?signin=abc").text  # the app, not a 404
        with client.websocket_connect("/api/sessions/stream?lang=tn") as socket:
            assert socket.receive_text() == "hello tn"
    assert started == ["up", "down"]


def test_api_paths_are_not_served_as_pages(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<!doctype html>")
    with TestClient(create_web(_api([]), tmp_path)) as client:
        assert client.get("/api/nothing-here").status_code == 404
