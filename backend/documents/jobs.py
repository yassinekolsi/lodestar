"""Reading uploads in the background (docs/plan/20).

An upload is checked at once (size, type, page count) and saved as a `processing` placeholder, so
the request returns in a second. The pages are then read here: plain text straight away, scanned
pages through OCR one page at a time, with the progress saved after each page so the app can show
"page 4 of 12". When it's done the document waits in `review` for the student to check it against
the original and validate it; if reading fails, it's `failed` with a reason the student can act on.

Tasks are kept in a set so they aren't garbage-collected while running. A restart can't resume a
task, so start-up marks anything still `processing` as failed (library.interrupted).
"""

import asyncio
import logging
from uuid import UUID
from weakref import WeakKeyDictionary

from sqlalchemy import select

from backend.agent.context import Services
from backend.db import tables as t
from backend.documents import library
from backend.documents.ingest import UnreadableDocument
from backend.documents.ocr import extract_document
from backend.registry.models import Registry

log = logging.getLogger(__name__)
_TASKS: set[asyncio.Task[None]] = set()
_SLOTS: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = WeakKeyDictionary()


def launch(
    services: Services,
    registry: Registry,
    user_id: UUID,
    doc_id: UUID,
    data: bytes,
    filename: str,
    force_ocr: bool,
) -> asyncio.Task[None]:
    task = asyncio.create_task(
        read(
            services,
            registry,
            user_id,
            doc_id,
            None if filename.lower().endswith(".pdf") else data,
            filename,
            force_ocr,
        ),
        name=f"read-document-{doc_id}",
    )
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return task


async def read(
    services: Services,
    registry: Registry,
    user_id: UUID,
    doc_id: UUID,
    data: bytes | None,
    filename: str,
    force_ocr: bool,
) -> None:
    # One PDF at a time keeps parser/embedding peaks bounded on a small host. Queued PDFs
    # live in Postgres, not in a growing queue of in-memory byte arrays.
    loop = asyncio.get_running_loop()
    slot = _SLOTS.setdefault(loop, asyncio.Semaphore(1))
    async with slot:
        if data is None:
            try:
                async with services.engine.connect() as conn:
                    data = await conn.scalar(
                        select(t.documents.c.source_pdf).where(
                            t.documents.c.user_id == user_id, t.documents.c.doc_id == doc_id
                        )
                    )
            except Exception:
                log.warning("could not load queued document %s", doc_id)
                await library.fail(
                    services.engine,
                    user_id,
                    doc_id,
                    "Could not load this file for reading. Please upload it again.",
                )
                return
            if data is None:
                return  # Removed while waiting to read.
        await _read(services, registry, user_id, doc_id, data, filename, force_ocr)


async def _read(
    services: Services,
    registry: Registry,
    user_id: UUID,
    doc_id: UUID,
    data: bytes,
    filename: str,
    force_ocr: bool,
) -> None:
    async def on_progress(pages_done: int) -> None:
        await library.set_progress(services.engine, user_id, doc_id, pages_done)

    try:
        doc = await extract_document(
            data,
            filename,
            registry,
            services.llm,
            user_id,
            force_gemini=force_ocr,
            on_progress=on_progress,
        )
        await library.finish(services.engine, services.memory, user_id, doc_id, doc)
    except UnreadableDocument as exc:
        await library.fail(services.engine, user_id, doc_id, str(exc))
    except Exception as exc:
        log.exception("reading document %s failed", doc_id)
        await library.fail(
            services.engine,
            user_id,
            doc_id,
            f"Something went wrong reading this file ({type(exc).__name__}). Try again.",
        )
