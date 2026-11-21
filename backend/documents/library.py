"""A student's document library (docs/plan/20): save an upload (Postgres rows, then the Qdrant
index), list, delete, and pick passages for a quiz. Every query filters by user."""

import logging
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from backend.contracts.common import Contract
from backend.contracts.events import LibraryChanged, LibraryPayload
from backend.db import tables as t
from backend.db.twin_store import append_event, user_scope
from backend.documents import questions
from backend.documents.ingest import Extracted
from backend.memory.store import MemoryStore
from backend.registry.models import Registry

log = logging.getLogger(__name__)
QUIZ_PASSAGES = 8


def requested_document(text: str) -> UUID | None:
    """Explicit chapter selection from a library action, never inferred from a title."""
    match = re.search(r"\[document:([0-9a-fA-F-]{36})\]", text)
    if match:
        try:
            return UUID(match.group(1))
        except ValueError:
            pass
    return None


class DocumentView(Contract):
    doc_id: UUID
    title: str
    filename: str
    subject_id: UUID | None = None
    chapter: str = ""
    pages: int
    passages: int
    concepts: dict[str, list[int]]
    created_at: datetime
    searchable: bool = True
    extraction_method: str = "text"
    review_required: bool = False
    status: str = "ready"
    progress: int = 0
    error: str | None = None


def _view(r: Any, searchable: bool | None = None) -> DocumentView:
    return DocumentView(
        doc_id=r.doc_id,
        title=r.title,
        filename=r.filename,
        subject_id=r.subject_id,
        chapter=r.chapter,
        pages=r.pages,
        passages=r.passages,
        concepts=dict(r.concepts or {}),
        created_at=r.created_at,
        searchable=(r.indexed and r.status == "ready") if searchable is None else searchable,
        extraction_method=getattr(r, "extraction_method", None)
        or (getattr(r, "extraction", None) or {}).get("method", "text"),
        review_required=r.review_required,
        status=r.status,
        progress=r.progress,
        error=r.error,
    )


async def save(
    engine: AsyncEngine,
    memory: MemoryStore | None,
    user_id: UUID,
    filename: str,
    doc: Extracted,
    subject_id: UUID | None = None,
    chapter: str = "",
    source_pdf: bytes | None = None,
) -> DocumentView:
    """Rows first (the source of truth), then the search index. If Qdrant is down the document is
    still saved and can be quizzed on; search comes back when the index is rebuilt."""
    doc_id = uuid4()
    rows = [
        {
            "passage_id": uuid4(),
            "doc_id": doc_id,
            "user_id": user_id,
            "page": p.page,
            "position": p.position,
            "text": p.text,
            "concepts": p.concepts,
        }
        for p in doc.passages
    ]
    async with engine.begin() as conn:
        await user_scope(conn, user_id)
        if subject_id is not None and not await conn.scalar(
            select(t.subjects.c.subject_id).where(
                t.subjects.c.user_id == user_id, t.subjects.c.subject_id == subject_id
            )
        ):
            raise ValueError("Choose one of your subjects first.")
        row = (
            await conn.execute(
                insert(t.documents)
                .values(
                    doc_id=doc_id,
                    user_id=user_id,
                    title=doc.title,
                    filename=filename[:200],
                    subject_id=subject_id,
                    chapter=chapter,
                    source_pdf=source_pdf,
                    extraction={
                        "method": doc.method,
                        "pages": doc.page_texts,
                        "warnings": doc.warnings,
                        "translations": doc.translations,
                    },
                    review_required=doc.review_required,
                    pages=doc.pages,
                    passages=len(rows),
                    concepts=doc.concepts(),
                )
                .returning(*(c for c in t.documents.c if c.name != "source_pdf"))
            )
        ).one()
        if rows:
            await conn.execute(insert(t.document_passages), rows)
        await append_event(
            conn,
            LibraryChanged(
                user_id=user_id,
                ts=datetime.now(UTC),
                payload=LibraryPayload(
                    action="document_uploaded", doc_id=doc_id, subject_id=subject_id
                ),
            ),
        )
    searchable = False
    if memory is not None and not doc.review_required:
        try:
            await memory.write_passages(user_id, doc_id, doc.title, rows)
            async with engine.begin() as conn:
                await user_scope(conn, user_id)
                await conn.execute(
                    update(t.documents)
                    .where(t.documents.c.user_id == user_id, t.documents.c.doc_id == doc_id)
                    .values(indexed=True)
                )
            searchable = True
        except Exception:
            log.warning(
                "Qdrant unavailable; document saved without its search index", exc_info=True
            )
    return _view(row, searchable)


async def documents(conn: AsyncConnection, user_id: UUID) -> list[DocumentView]:
    rows = await conn.execute(
        select(
            *(c for c in t.documents.c if c.name not in {"source_pdf", "extraction"}),
            t.documents.c.extraction["method"].astext.label("extraction_method"),
        )
        .where(t.documents.c.user_id == user_id)
        .order_by(t.documents.c.created_at.desc())
    )
    return [_view(r) for r in rows]


async def has_documents(conn: AsyncConnection, user_id: UUID, *, ready_only: bool = False) -> bool:
    """Whether the student has uploaded anything; with `ready_only`, anything they have checked
    and validated, which is what answers and quizzes use."""
    q = select(func.count()).select_from(t.documents).where(t.documents.c.user_id == user_id)
    if ready_only:
        q = q.where(t.documents.c.review_required.is_(False), t.documents.c.status == "ready")
    return bool((await conn.execute(q)).scalar_one())


async def remove(
    engine: AsyncEngine, memory: MemoryStore | None, user_id: UUID, doc_id: UUID
) -> bool:
    async with engine.begin() as conn:
        await user_scope(conn, user_id)
        gone = await conn.execute(
            delete(t.documents).where(
                t.documents.c.doc_id == doc_id, t.documents.c.user_id == user_id
            )
        )
        if gone.rowcount:
            await append_event(
                conn,
                LibraryChanged(
                    user_id=user_id,
                    ts=datetime.now(UTC),
                    payload=LibraryPayload(action="document_deleted", doc_id=doc_id),
                ),
            )
    if memory is not None:
        try:
            await memory.delete_document(user_id, doc_id)
        except Exception:
            log.warning(
                "Qdrant unavailable; document index left to the next cleanup", exc_info=True
            )
    return bool(gone.rowcount)


async def passages(
    conn: AsyncConnection, user_id: UUID, doc_id: UUID | None = None, concept: str | None = None
) -> tuple[str, str, list[questions.Source]]:
    """Passages to quiz on: those about `concept` if it's named (from any document), else the
    latest document's, spread across it. Returns (doc id, title, sources)."""
    q = select(
        t.document_passages.c.doc_id,
        t.document_passages.c.page,
        t.document_passages.c.position,
        t.document_passages.c.text,
        t.document_passages.c.concepts,
        t.documents.c.title,
    ).join(t.documents, t.documents.c.doc_id == t.document_passages.c.doc_id)
    q = q.where(t.document_passages.c.user_id == user_id)
    q = q.where(t.documents.c.review_required.is_(False))
    if doc_id is not None:
        q = q.where(t.document_passages.c.doc_id == doc_id)
    elif concept is not None:
        q = q.where(t.document_passages.c.concepts.any(concept))
    else:
        latest = (
            select(t.documents.c.doc_id)
            .where(t.documents.c.user_id == user_id)
            .order_by(t.documents.c.created_at.desc())
            .limit(1)
            .scalar_subquery()
        )
        q = q.where(t.document_passages.c.doc_id == latest)
    rows = (await conn.execute(q.order_by(t.document_passages.c.position))).all()
    if not rows:
        return "", "", []
    step = max(1, len(rows) // QUIZ_PASSAGES)
    chosen = rows[::step][:QUIZ_PASSAGES] if concept is None else rows[:QUIZ_PASSAGES]
    sources = [questions.Source(r.text, r.page, list(r.concepts)) for r in chosen]
    all_sources = [questions.Source(r.text, r.page, list(r.concepts)) for r in rows]
    # Code questions look across the whole document for terms; the model sees the chosen few.
    return str(rows[0].doc_id), rows[0].title, sources if len(all_sources) > 40 else all_sources


def vocabulary(registry: Registry) -> list[str]:
    """Course terms the code questions may ask about: concept names and multi-word aliases."""
    out: list[str] = []
    for course in registry.courses:
        for c in course.concepts:
            out.append(c.name)
            out += [a for a in c.aliases if " " in a and "(" not in a]
    return out


async def quiz_content(
    conn: AsyncConnection,
    user_id: UUID,
    registry: Registry,
    seed: int,
    concept: str | None = None,
    draft: Any = None,
    doc_id: UUID | None = None,
) -> tuple[dict[str, Any] | None, dict[str, float]]:
    """A quiz from the student's own document, and the concepts it counts for (0.5 each: questions
    from notes aren't calibrated). `draft` is an async callable (prompt -> DraftQuiz) when a model
    is available. None when there's no document or too little text to ask about."""
    document_id, title, sources = await passages(conn, user_id, concept=concept, doc_id=doc_id)
    if not sources:
        return None, {}
    made: list[dict[str, Any]] = []
    made_by = "code"
    if draft is not None:
        try:
            made = questions.checked(await draft(questions.prompt(sources)), sources, seed)
            made_by = "model, checked by code" if made else "code"
        except Exception:
            log.info("no model for document questions; using the text itself", exc_info=True)
    if len(made) < questions.QUESTIONS:
        made += questions.from_text(
            sources, vocabulary(registry), seed, questions.QUESTIONS - len(made)
        )
    if not made:
        return None, {}
    concepts = sorted({c for q in made for c in q["concepts"]} | ({concept} if concept else set()))
    return questions.as_content(made[: questions.QUESTIONS], title, document_id, made_by), {
        c: 0.5 for c in concepts if registry.course_of(c)
    }


def cite(hits: Sequence[Any]) -> list[dict[str, Any]]:
    return [{"title": h.title, "page": h.page, "text": h.text, "doc_id": h.doc_id} for h in hits]


# Background reading (docs/plan/20) -----------------------------------------------------------


async def start(
    engine: AsyncEngine,
    user_id: UUID,
    filename: str,
    pages: int,
    subject_id: UUID | None,
    chapter: str,
    source_pdf: bytes | None,
) -> DocumentView:
    """A placeholder row the student sees at once, while the pages are read in the background."""
    async with engine.begin() as conn:
        await user_scope(conn, user_id)
        if subject_id is not None and not await conn.scalar(
            select(t.subjects.c.subject_id).where(
                t.subjects.c.user_id == user_id, t.subjects.c.subject_id == subject_id
            )
        ):
            raise ValueError("Choose one of your subjects first.")
        title = filename.rsplit(".", 1)[0].replace("_", " ")[:120] or "Document"
        row = (
            await conn.execute(
                insert(t.documents)
                .values(
                    user_id=user_id,
                    title=title,
                    filename=filename[:200],
                    subject_id=subject_id,
                    chapter=chapter,
                    source_pdf=source_pdf,
                    review_required=True,
                    status="processing",
                    pages=pages,
                    passages=0,
                )
                .returning(*(c for c in t.documents.c if c.name != "source_pdf"))
            )
        ).one()
    return _view(row)


async def set_progress(engine: AsyncEngine, user_id: UUID, doc_id: UUID, pages_done: int) -> None:
    async with engine.begin() as conn:
        await user_scope(conn, user_id)
        await conn.execute(
            update(t.documents)
            .where(t.documents.c.user_id == user_id, t.documents.c.doc_id == doc_id)
            .values(progress=pages_done)
        )


async def finish(
    engine: AsyncEngine,
    memory: MemoryStore | None,
    user_id: UUID,
    doc_id: UUID,
    doc: Extracted,
) -> None:
    """The pages are read: store them and embed them right away, so validating is instant. Search
    and quizzes still skip the document until the student validates it."""
    rows = [
        {
            "passage_id": uuid4(),
            "doc_id": doc_id,
            "user_id": user_id,
            "page": p.page,
            "position": p.position,
            "text": p.text,
            "concepts": p.concepts,
        }
        for p in doc.passages
    ]
    async with engine.begin() as conn:
        await user_scope(conn, user_id)
        await conn.execute(
            delete(t.document_passages).where(
                t.document_passages.c.doc_id == doc_id, t.document_passages.c.user_id == user_id
            )
        )
        if rows:
            await conn.execute(insert(t.document_passages), rows)
        row = (
            await conn.execute(
                update(t.documents)
                .where(t.documents.c.user_id == user_id, t.documents.c.doc_id == doc_id)
                .values(
                    title=doc.title,
                    pages=doc.pages,
                    progress=doc.pages,
                    passages=len(rows),
                    concepts=doc.concepts(),
                    extraction={
                        "method": doc.method,
                        "pages": doc.page_texts,
                        "warnings": doc.warnings,
                        "translations": doc.translations,
                    },
                    review_required=True,
                    status="review",
                    error=None,
                )
                .returning(t.documents.c.subject_id, t.documents.c.title)
            )
        ).one_or_none()
        if row is None:
            return
        await append_event(
            conn,
            LibraryChanged(
                user_id=user_id,
                ts=datetime.now(UTC),
                payload=LibraryPayload(
                    action="document_uploaded", doc_id=doc_id, subject_id=row.subject_id
                ),
            ),
        )
    await index(engine, memory, user_id, doc_id, row.title, rows)


async def index(
    engine: AsyncEngine,
    memory: MemoryStore | None,
    user_id: UUID,
    doc_id: UUID,
    title: str,
    rows: list[dict[str, Any]],
) -> bool:
    """Embed the passages into Qdrant and record whether it worked. Postgres stays the source of
    truth: if Qdrant is down the document is still usable and is indexed again later."""
    indexed = False
    if memory is not None:
        try:
            await memory.delete_document(user_id, doc_id)
            await memory.write_passages(user_id, doc_id, title, rows)
            indexed = True
        except Exception:
            log.warning("Qdrant unavailable; document saved without its index", exc_info=True)
    async with engine.begin() as conn:
        await user_scope(conn, user_id)
        await conn.execute(
            update(t.documents)
            .where(t.documents.c.user_id == user_id, t.documents.c.doc_id == doc_id)
            .values(indexed=indexed)
        )
    return indexed


async def fail(engine: AsyncEngine, user_id: UUID, doc_id: UUID, reason: str) -> None:
    async with engine.begin() as conn:
        await user_scope(conn, user_id)
        await conn.execute(
            update(t.documents)
            .where(t.documents.c.user_id == user_id, t.documents.c.doc_id == doc_id)
            .values(status="failed", error=reason[:500])
        )


async def interrupted(engine: AsyncEngine) -> int:
    """At start-up: reading cut off by a restart cannot resume, so it is marked failed."""
    async with engine.begin() as conn:
        done = await conn.execute(
            update(t.documents)
            .where(t.documents.c.status == "processing")
            .values(status="failed", error="Reading was interrupted. Upload the file again.")
        )
    return int(done.rowcount or 0)


_REINDEX: set[Any] = set()


def launch_reindex(engine: AsyncEngine, memory: MemoryStore) -> None:
    """In the background: put every validated chapter into a newly created search collection,
    one document at a time (bounded memory), from the passages kept in Postgres."""
    import asyncio

    task = asyncio.create_task(reindex_all(engine, memory), name="reindex-chapters")
    _REINDEX.add(task)
    task.add_done_callback(_REINDEX.discard)


async def reindex_all(engine: AsyncEngine, memory: MemoryStore) -> int:
    async with engine.connect() as conn:
        docs = (
            await conn.execute(
                select(t.documents.c.user_id, t.documents.c.doc_id, t.documents.c.title).where(
                    t.documents.c.status.in_(("ready", "review"))
                )
            )
        ).all()
    done = 0
    for doc in docs:
        try:
            async with engine.begin() as conn:
                await user_scope(conn, doc.user_id)
                rows = [
                    dict(r._mapping)
                    for r in await conn.execute(
                        select(t.document_passages).where(
                            t.document_passages.c.doc_id == doc.doc_id,
                            t.document_passages.c.user_id == doc.user_id,
                        )
                    )
                ]
            if await index(engine, memory, doc.user_id, doc.doc_id, doc.title, rows):
                done += 1
        except Exception:
            log.warning("re-indexing document %s failed", doc.doc_id, exc_info=True)
    log.info("re-indexed %d of %d chapters", done, len(docs))
    return done


async def approve(
    engine: AsyncEngine, memory: MemoryStore | None, user_id: UUID, doc_id: UUID
) -> DocumentView | None:
    """The student checked the document against the original: it becomes searchable."""
    async with engine.begin() as conn:
        await user_scope(conn, user_id)
        doc = (
            await conn.execute(
                select(*(c for c in t.documents.c if c.name != "source_pdf"))
                .where(t.documents.c.user_id == user_id, t.documents.c.doc_id == doc_id)
                .with_for_update()
            )
        ).one_or_none()
        if doc is None:
            return None
        if doc.status not in ("review", "ready"):
            raise ValueError("This document is not ready to validate yet.")
        if any("[unclear]" in p for p in (doc.extraction or {}).get("pages", [])):
            raise ValueError("Some pages have unclear symbols. Fix them in the review first.")
        rows = [
            dict(r._mapping)
            for r in await conn.execute(
                select(t.document_passages).where(
                    t.document_passages.c.doc_id == doc_id,
                    t.document_passages.c.user_id == user_id,
                )
            )
        ]
        await conn.execute(
            update(t.documents)
            .where(t.documents.c.doc_id == doc_id)
            .values(review_required=False, status="ready")
        )
        await append_event(
            conn,
            LibraryChanged(
                user_id=user_id,
                ts=datetime.now(UTC),
                payload=LibraryPayload(action="document_reviewed", doc_id=doc_id),
            ),
        )
    indexed = bool(doc.indexed)
    if not indexed and memory is not None:
        try:
            await memory.delete_document(user_id, doc_id)
            await memory.write_passages(user_id, doc_id, doc.title, rows)
            indexed = True
        except Exception:
            log.warning("Qdrant unavailable; document validated without its index", exc_info=True)
    async with engine.begin() as conn:
        await user_scope(conn, user_id)
        row = (
            await conn.execute(
                update(t.documents)
                .where(t.documents.c.user_id == user_id, t.documents.c.doc_id == doc_id)
                .values(indexed=indexed)
                .returning(*(c for c in t.documents.c if c.name != "source_pdf"))
            )
        ).one()
    return _view(row)
