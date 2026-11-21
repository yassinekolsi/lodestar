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

from backend.agent.context import Services
from backend.documents import library
from backend.documents.ingest import UnreadableDocument
from backend.documents.ocr import Transcription, extract_document
from backend.registry.models import Registry

log = logging.getLogger(__name__)
_TASKS: set[asyncio.Task[None]] = set()


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
        read(services, registry, user_id, doc_id, data, filename, force_ocr),
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
    data: bytes,
    filename: str,
    force_ocr: bool,
) -> None:
    done = 0

    async def on_page(_: int, __: Transcription) -> None:
        nonlocal done
        done += 1
        await library.set_progress(services.engine, user_id, doc_id, done)

    try:
        doc = await extract_document(
            data, filename, registry, services.llm, user_id, force_gemini=force_ocr, on_page=on_page
        )
        await library.finish(services.engine, user_id, doc_id, doc)
    except UnreadableDocument as exc:
        await library.fail(services.engine, user_id, doc_id, str(exc))
    except Exception:
        log.exception("reading document %s failed", doc_id)
        await library.fail(
            services.engine, user_id, doc_id, "Something went wrong reading this file. Try again."
        )
