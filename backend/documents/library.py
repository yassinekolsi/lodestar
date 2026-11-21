"""A student's document library (docs/plan/20): save an upload (Postgres rows, then the Qdrant
index), list, delete, and pick passages for a quiz. Every query filters by user."""

import logging
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from backend.contracts.common import Contract
from backend.db import tables as t
from backend.db.twin_store import user_scope
from backend.documents import questions
from backend.documents.ingest import Extracted
from backend.memory.store import MemoryStore
from backend.registry.models import Registry

log = logging.getLogger(__name__)
QUIZ_PASSAGES = 8


class DocumentView(Contract):
    doc_id: UUID
    title: str
    filename: str
    pages: int
    passages: int
    concepts: dict[str, list[int]]
    created_at: datetime
    searchable: bool = True


def _view(r: Any, searchable: bool = True) -> DocumentView:
    return DocumentView(
        doc_id=r.doc_id,
        title=r.title,
        filename=r.filename,
        pages=r.pages,
        passages=r.passages,
        concepts=dict(r.concepts or {}),
        created_at=r.created_at,
        searchable=searchable,
    )


async def save(
    engine: AsyncEngine,
    memory: MemoryStore | None,
    user_id: UUID,
    filename: str,
    doc: Extracted,
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
        row = (
            await conn.execute(
                insert(t.documents)
                .values(
                    doc_id=doc_id,
                    user_id=user_id,
                    title=doc.title,
                    filename=filename[:200],
                    pages=doc.pages,
                    passages=len(rows),
                    concepts=doc.concepts(),
                )
                .returning(t.documents)
            )
        ).one()
        if rows:
            await conn.execute(insert(t.document_passages), rows)
    searchable = False
    if memory is not None:
        try:
            await memory.write_passages(user_id, doc_id, doc.title, rows)
            searchable = True
        except Exception:
            log.warning(
                "Qdrant unavailable; document saved without its search index", exc_info=True
            )
    return _view(row, searchable)


async def documents(conn: AsyncConnection, user_id: UUID) -> list[DocumentView]:
    rows = await conn.execute(
        select(t.documents)
        .where(t.documents.c.user_id == user_id)
        .order_by(t.documents.c.created_at.desc())
    )
    return [_view(r) for r in rows]


async def has_documents(conn: AsyncConnection, user_id: UUID) -> bool:
    n = (
        await conn.execute(
            select(func.count()).select_from(t.documents).where(t.documents.c.user_id == user_id)
        )
    ).scalar_one()
    return bool(n)


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
    if concept is not None:
        q = q.where(t.document_passages.c.concepts.any(concept))
    elif doc_id is not None:
        q = q.where(t.document_passages.c.doc_id == doc_id)
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
) -> tuple[dict[str, Any] | None, dict[str, float]]:
    """A quiz from the student's own document, and the concepts it counts for (0.5 each: questions
    from notes aren't calibrated). `draft` is an async callable (prompt -> DraftQuiz) when a model
    is available. None when there's no document or too little text to ask about."""
    doc_id, title, sources = await passages(conn, user_id, concept=concept)
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
    return questions.as_content(made[: questions.QUESTIONS], title, doc_id, made_by), {
        c: 0.5 for c in concepts if registry.course_of(c)
    }


def cite(hits: Sequence[Any]) -> list[dict[str, Any]]:
    return [{"title": h.title, "page": h.page, "text": h.text, "doc_id": h.doc_id} for h in hits]
