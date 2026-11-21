"""The "Demo" button: sign this browser in as the demo user (Alex, from `backend.db.seed`), seeding
them on first use. Off with LODESTAR_DEMO=0, for a deployment open to the public."""

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status
from starlette.concurrency import run_in_threadpool

from backend.config import get_settings
from backend.contracts.common import Contract
from backend.contracts.views import CreatedUser
from backend.db.engine import get_engine
from backend.db.seed import demo_sign_in
from backend.db.seed_memory import seed_memory

router = APIRouter(tags=["users"])
log = logging.getLogger(__name__)


def _sign_in() -> tuple[CreatedUser, bool]:
    with get_engine().begin() as conn:
        user_id, token, created = demo_sign_in(conn)
    return CreatedUser(user_id=user_id, token=token), created


class PreparingDemo(Contract):
    status: Literal["preparing"] = "preparing"


async def _memory_notes(user: CreatedUser, request: Request) -> None:
    memory = getattr(getattr(request.app.state, "services", None), "memory", None)
    try:
        if memory is not None:
            await seed_memory(user.user_id, memory)
    except Exception:
        log.warning("Demo memory notes skipped", exc_info=True)


@router.post("/demo", response_model=CreatedUser | PreparingDemo)
async def post_demo(
    request: Request, response: Response, background_tasks: BackgroundTasks
) -> CreatedUser | PreparingDemo:
    """A bearer token for the demo user, who has four months of practice to look around in."""
    if not get_settings().demo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The demo is switched off here.")
    # First-use seeding can involve many database round trips. Keep each HTTP request short
    # while one shared task prepares the demo, instead of holding it open through a gateway.
    task: asyncio.Task[tuple[CreatedUser, bool]] | None = getattr(
        request.app.state, "demo_preparation", None
    )
    if task is None:
        task = asyncio.create_task(run_in_threadpool(_sign_in))
        request.app.state.demo_preparation = task
    try:
        user, created = await asyncio.wait_for(asyncio.shield(task), timeout=0.75)
    except TimeoutError:
        response.status_code = status.HTTP_202_ACCEPTED
        return PreparingDemo()
    except Exception:
        request.app.state.demo_preparation = None
        raise
    request.app.state.demo_preparation = None
    if created:
        background_tasks.add_task(_memory_notes, user, request)
    return user
