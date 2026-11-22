"""Shared FastAPI dependencies: database access and the current user."""

import re
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from backend import course_scope
from backend.db import tables as t
from backend.db.engine import get_async_engine
from backend.db.twin_store import user_for_token, user_scope
from backend.registry.loader import load_registry
from backend.registry.models import Registry


def engine_dep() -> AsyncEngine:
    return get_async_engine()


def registry_dep() -> Registry:
    return load_registry()


# The demo person is shared by every visitor, so nobody may change what the next visitor sees or
# spends: uploads, subjects, AI keys and model choice, consent, deleting data, settings.
# Studying (sessions, quiz answers) stays open, or the demo would show nothing.
DEMO_READ_ONLY = re.compile(r"^/(documents|subjects|llm|consent|experiments|me)(/|$)")


async def current_user(
    request: Request,
    engine: Annotated[AsyncEngine, Depends(engine_dep)],
    authorization: Annotated[str | None, Header()] = None,
) -> UUID:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    async with engine.begin() as conn:
        user_id = await user_for_token(conn, authorization.split(" ", 1)[1].strip())
        if user_id is not None:
            # Their own uploads, or the built-in course for the demo (backend/course_scope.py).
            await course_scope.scope(conn, user_id)
            if request.method not in ("GET", "HEAD", "OPTIONS") and DEMO_READ_ONLY.match(
                request.url.path.removeprefix("/api")
            ):
                name = await conn.scalar(
                    select(t.users.c.display_name).where(t.users.c.user_id == user_id)
                )
                if course_scope.is_demo(name):
                    raise HTTPException(
                        status.HTTP_403_FORBIDDEN,
                        "The demo is shared by every visitor, so it can't be changed. Sign up "
                        "with your own documents to do this.",
                    )
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown token")
    return user_id


async def conn_dep(
    engine: Annotated[AsyncEngine, Depends(engine_dep)],
    user_id: Annotated[UUID, Depends(current_user)],
) -> AsyncIterator[AsyncConnection]:
    """A read connection limited to the signed-in user's rows (row-level security). Writes open
    their own transaction inside the handler (`async with engine.begin()`), because a yield
    dependency's exit code can run after the response is sent: a client could act on a reply
    before its write was committed."""
    async with engine.connect() as conn:
        await user_scope(conn, user_id)
        yield conn


Engine = Annotated[AsyncEngine, Depends(engine_dep)]
Conn = Annotated[AsyncConnection, Depends(conn_dep)]
CurrentUser = Annotated[UUID, Depends(current_user)]
RegistryDep = Annotated[Registry, Depends(registry_dep)]
