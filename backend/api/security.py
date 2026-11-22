"""Security headers on every response and per-IP rate limits on the endpoints that cost money
(model calls on the operator's key) or storage (uploads, new accounts).

The limits are kept in memory: one Render instance, and a restart only resets the counters.
Behind Render the client address is the first X-Forwarded-For entry; a direct loopback call
(tests, local development) is not limited.
"""

import json
import re
import time
from collections import deque
from collections.abc import MutableMapping
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

CSP = "; ".join(
    [
        "default-src 'self'",
        # Voice: the TTS model's runtime comes from jsDelivr; audio worklets load from blob URLs.
        "script-src 'self' 'wasm-unsafe-eval' blob: https://cdn.jsdelivr.net",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob: https:",
        "font-src 'self' data:",
        "media-src 'self' data: blob:",
        "connect-src 'self' https:",
        "worker-src 'self' blob:",
        "frame-src 'self' blob:",  # the original PDF beside its transcription
        "frame-ancestors 'none'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
)
HEADERS = [
    (b"content-security-policy", CSP.encode()),
    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
    (b"x-frame-options", b"DENY"),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(), geolocation=(), microphone=(self)"),
]


class SecurityHeaders:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                present = {k.lower() for k, _ in message.get("headers", [])}
                message["headers"] = [
                    *message.get("headers", []),
                    *((k, v) for k, v in HEADERS if k not in present),
                ]
            await send(message)

        await self.app(scope, receive, with_headers)


# (method, path pattern, requests allowed, window in seconds). Paths are the API's own, without
# the /api prefix the web wrapper strips.
LIMITS: list[tuple[str, re.Pattern[str], int, int]] = [
    ("POST", re.compile(r"^/users$"), 10, 3600),
    ("POST", re.compile(r"^/demo$"), 30, 3600),
    ("POST", re.compile(r"^/documents$"), 20, 3600),
    ("POST", re.compile(r"^/sessions(/[^/]+/(messages|resume))?$"), 60, 600),
    ("POST", re.compile(r"^/transcribe$"), 30, 600),
]
LOOPBACK = {"127.0.0.1", "::1", "testclient"}


def client_ip(scope: Scope) -> str:
    for name, value in scope.get("headers", []):
        if name == b"x-forwarded-for":
            return str(value.decode("latin-1")).split(",")[0].strip()
    client = scope.get("client")
    return str(client[0]) if client else "unknown"


class RateLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.hits: MutableMapping[tuple[str, int], deque[float]] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            ip = client_ip(scope)
            if ip not in LOOPBACK:
                for i, (method, pattern, allowed, window) in enumerate(LIMITS):
                    if scope["method"] == method and pattern.match(scope["path"]):
                        if not self._allow((ip, i), allowed, window):
                            await _too_many(send, window)
                            return
                        break
        await self.app(scope, receive, send)

    def _allow(self, key: tuple[str, int], allowed: int, window: int) -> bool:
        now = time.monotonic()
        if len(self.hits) > 50_000:  # bound memory: forget clients idle for an hour
            for k in [k for k, q in self.hits.items() if not q or now - q[-1] > 3600]:
                del self.hits[k]
        q = self.hits.setdefault(key, deque())
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= allowed:
            return False
        q.append(now)
        return True


async def _too_many(send: Send, window: int) -> None:
    body: dict[str, Any] = {"detail": "Too many requests. Please wait a few minutes."}
    await send(
        {
            "type": "http.response.start",
            "status": 429,
            "headers": [
                (b"content-type", b"application/json"),
                (b"retry-after", str(min(window, 600)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": json.dumps(body).encode()})
