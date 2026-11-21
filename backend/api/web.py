"""One server for a hosted deployment (Dockerfile, render.yaml): the API under /api, the built
frontend everywhere else.

In development Vite serves the frontend and proxies /api to the backend (frontend/vite.config.ts).
Hosted, there is no Vite: this app does the same in one process, so the pages, the API and the
WebSockets share one origin and need no CORS. The API is the same app as `backend.api.main:app`,
with its lifespan (database pools, Qdrant, the graph) run once here.
"""

import os
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

API_PREFIX = "/api"


class SinglePage(StaticFiles):
    """Static files, with index.html for any path that isn't a file (the app reads its state from
    the query string, but a reload on any path should still open it)."""

    async def get_response(self, path: str, scope: MutableMapping[str, Any]) -> Response:
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)
        if response.status_code == 404:
            return await super().get_response("index.html", scope)
        return response


def create_web(api: ASGIApp, web_dir: Path) -> ASGIApp:
    static = SinglePage(directory=web_dir, html=True, check_dir=False)

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":  # the API's startup and shutdown
            await api(scope, receive, send)
            return
        path: str = scope.get("path", "")
        if path == API_PREFIX or path.startswith(API_PREFIX + "/"):
            # The backend's routes sit at the root, as behind the Vite proxy.
            child = dict(scope)
            child["path"] = path[len(API_PREFIX) :] or "/"
            raw = scope.get("raw_path")
            if isinstance(raw, bytes) and raw.startswith(API_PREFIX.encode()):
                child["raw_path"] = raw[len(API_PREFIX) :] or b"/"
            await api(child, receive, send)
            return
        if scope["type"] == "http":
            await static(scope, receive, send)
            return
        # A WebSocket outside /api has nothing to talk to.
        await send({"type": "websocket.close", "code": 1000})

    return app


def _app() -> ASGIApp:
    from backend.api.main import app as api

    return create_web(api, Path(os.environ.get("LODESTAR_WEB_DIR", "web")))


app = _app()
