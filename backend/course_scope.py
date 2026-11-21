"""Who studies the built-in course (registry/courses/).

A real student studies their own material: the subjects and chapters they upload (docs/plan/20).
The built-in Probability 1 course is the demo's: the demo person (Alex) and the classmates seeded
with them, so the concept map, the gap rule and the class view can be shown without uploading
anything. `LODESTAR_BUILT_IN_COURSE=all` gives every account the built-in course (local
experiments, and the test suite, which exercises the course with fresh users).

Like the language (backend/i18n.py), the answer is kept in a context variable for the request,
so the registry hands out the course only where it applies (Registry.courses_in). Outside a
request (seeding, background jobs, scripts) the course is on.
"""

from contextvars import ContextVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from backend.config import get_settings
from backend.db import tables as t

# The names the demo seed gives its people (backend/db/seed.py). Sign-up never sets a name.
DEMO_NAME = "Alex"
CLASSMATE_PREFIX = "Classmate "

_enabled: ContextVar[bool] = ContextVar("lodestar_built_in_course", default=True)


def enabled() -> bool:
    return _enabled.get()


def set_enabled(value: bool) -> None:
    _enabled.set(value)


def is_demo(display_name: str | None) -> bool:
    return bool(display_name) and (
        display_name == DEMO_NAME or str(display_name).startswith(CLASSMATE_PREFIX)
    )


async def for_user(conn: AsyncConnection, user_id: UUID) -> bool:
    """Whether this account studies the built-in course."""
    if get_settings().built_in_course == "all":
        return True
    name = (
        await conn.execute(select(t.users.c.display_name).where(t.users.c.user_id == user_id))
    ).scalar_one_or_none()
    return is_demo(name)


async def scope(conn: AsyncConnection, user_id: UUID) -> bool:
    """Decide for this request and remember it; returns the decision."""
    on = await for_user(conn, user_id)
    set_enabled(on)
    return on
