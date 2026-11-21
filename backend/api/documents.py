"""The student's own course documents (docs/plan/20): upload a PDF or text file, list, search
with page citations, delete."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Request, Response, UploadFile, status
from pydantic import Field
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from backend.agent.context import Services
from backend.agent.intents import skills_in
from backend.api.deps import Conn, CurrentUser, RegistryDep
from backend.contracts.common import Contract
from backend.contracts.events import LibraryChanged, LibraryPayload
from backend.db import tables as t
from backend.db.twin_store import append_event, user_scope
from backend.documents import jobs, library
from backend.documents.ingest import (
    MAX_BYTES,
    UnreadableDocument,
    pages_of,
    scanned_pages,
    split_passages,
)
from backend.documents.math_text import math_issues
from backend.documents.ocr import OCR_MAX_PAGES

router = APIRouter(tags=["documents"])


class SubjectInput(Contract):
    name: str = Field(min_length=1, max_length=100, pattern=r".*\S.*")


class SubjectView(Contract):
    subject_id: UUID
    name: str


@router.get("/subjects", response_model=list[SubjectView])
async def subjects(conn: Conn, user_id: CurrentUser) -> list[SubjectView]:
    rows = await conn.execute(
        select(t.subjects).where(t.subjects.c.user_id == user_id).order_by(t.subjects.c.name)
    )
    return [SubjectView(subject_id=r.subject_id, name=r.name) for r in rows]


@router.post("/subjects", response_model=SubjectView, status_code=201)
async def create_subject(body: SubjectInput, request: Request, user_id: CurrentUser) -> SubjectView:
    services: Services = request.app.state.services
    try:
        async with services.engine.begin() as conn:
            await user_scope(conn, user_id)
            row = (
                await conn.execute(
                    insert(t.subjects)
                    .values(user_id=user_id, name=body.name.strip())
                    .returning(t.subjects)
                )
            ).one()
            await append_event(
                conn,
                LibraryChanged(
                    user_id=user_id,
                    ts=datetime.now(UTC),
                    payload=LibraryPayload(action="subject_created", subject_id=row.subject_id),
                ),
            )
    except IntegrityError as exc:
        raise HTTPException(409, "You already have a subject with that name.") from exc
    return SubjectView(subject_id=row.subject_id, name=row.name)


class PassageView(Contract):
    doc_id: str
    title: str
    page: int
    text: str
    concepts: list[str] = Field(default_factory=list)
    score: float


@router.post("/documents", response_model=library.DocumentView, status_code=202)
async def upload(
    file: UploadFile,
    request: Request,
    user_id: CurrentUser,
    registry: RegistryDep,
    subject_id: Annotated[UUID | None, Form()] = None,
    chapter: Annotated[str, Form(max_length=120)] = "",
    gemini: Annotated[bool, Form()] = False,
) -> library.DocumentView:
    """Checks the file at once and returns a `processing` document; the pages are read in the
    background (OCR can take minutes), and GET /documents shows the progress."""
    services: Services = request.app.state.services
    filename = file.filename or "document.pdf"
    data = await file.read(MAX_BYTES + 1)
    try:
        pages, _ = await run_in_threadpool(pages_of, data, filename, allow_scans=True)
    except UnreadableDocument as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    is_pdf = filename.lower().endswith(".pdf")
    to_read = len(pages) if gemini else len(scanned_pages(pages)) if is_pdf else 0
    if to_read > OCR_MAX_PAGES:
        raise HTTPException(
            422, f"Split scanned PDFs into files of at most {OCR_MAX_PAGES} pages for OCR."
        )
    try:
        doc = await library.start(
            services.engine,
            user_id,
            filename,
            len(pages),
            subject_id,
            chapter.strip(),
            data if is_pdf else None,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    jobs.launch(services, registry, user_id, doc.doc_id, data, filename, gemini)
    return doc


@router.post("/documents/{doc_id}/approve", response_model=library.DocumentView)
async def approve_document(
    doc_id: UUID, request: Request, user_id: CurrentUser
) -> library.DocumentView:
    """The student looked at the document next to the original and validated it."""
    services: Services = request.app.state.services
    try:
        doc = await library.approve(services.engine, services.memory, user_id, doc_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if doc is None:
        raise HTTPException(404, "No such document")
    return doc


@router.get("/documents", response_model=list[library.DocumentView])
async def list_documents(conn: Conn, user_id: CurrentUser) -> list[library.DocumentView]:
    return await library.documents(conn, user_id)


@router.get("/documents/search", response_model=list[PassageView])
async def search(
    q: str, request: Request, user_id: CurrentUser, doc_id: UUID | None = None
) -> list[PassageView]:
    services: Services = request.app.state.services
    if services.memory is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Search is offline right now")
    hits = await services.memory.search_documents(user_id, q[:500], limit=5, doc_id=doc_id)
    async with services.engine.connect() as conn:
        allowed = set(
            (
                await conn.execute(
                    select(t.documents.c.doc_id).where(
                        t.documents.c.user_id == user_id, t.documents.c.review_required.is_(False)
                    )
                )
            ).scalars()
        )
    return [
        PassageView(
            doc_id=h.doc_id,
            title=h.title,
            page=h.page,
            text=h.text,
            concepts=h.concepts,
            score=round(h.score, 4),
        )
        for h in hits
        if UUID(h.doc_id) in allowed
    ]


class ReviewPage(Contract):
    page: int
    text: str
    warnings: list[str]


class ReviewInput(Contract):
    pages: list[str] = Field(min_length=1, max_length=400)


@router.get("/documents/{doc_id}/pages", response_model=list[ReviewPage])
async def document_pages(doc_id: UUID, conn: Conn, user_id: CurrentUser) -> list[ReviewPage]:
    row = (
        await conn.execute(
            select(*(c for c in t.documents.c if c.name != "source_pdf")).where(
                t.documents.c.doc_id == doc_id, t.documents.c.user_id == user_id
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "No such document")
    extraction = row.extraction or {}
    texts = extraction.get("pages", [])
    if not texts:
        rows = (
            await conn.execute(
                select(t.document_passages)
                .where(
                    t.document_passages.c.doc_id == doc_id, t.document_passages.c.user_id == user_id
                )
                .order_by(t.document_passages.c.position)
            )
        ).all()
        texts = ["\n".join(p.text for p in rows if p.page == i) for i in range(1, row.pages + 1)]
    warnings = extraction.get("warnings", {})
    return [
        ReviewPage(page=i + 1, text=text, warnings=warnings.get(str(i + 1), []))
        for i, text in enumerate(texts)
    ]


@router.get("/documents/{doc_id}/original")
async def original(doc_id: UUID, conn: Conn, user_id: CurrentUser) -> Response:
    data = await conn.scalar(
        select(t.documents.c.source_pdf).where(
            t.documents.c.doc_id == doc_id, t.documents.c.user_id == user_id
        )
    )
    if data is None:
        raise HTTPException(404, "The original PDF is not available for this upload.")
    return Response(
        bytes(data),
        media_type="application/pdf",
        headers={"Content-Disposition": "inline; filename=course.pdf", "Cache-Control": "no-store"},
    )


@router.put("/documents/{doc_id}/review", response_model=library.DocumentView)
async def review_document(
    doc_id: UUID,
    body: ReviewInput,
    request: Request,
    user_id: CurrentUser,
    registry: RegistryDep,
) -> library.DocumentView:
    if sum(len(p) for p in body.pages) > 5_000_000 or any("[unclear]" in p for p in body.pages):
        raise HTTPException(422, "Resolve every [unclear] marker before approving these pages.")
    if any(math_issues(page) for page in body.pages):
        raise HTTPException(422, "Fix unbalanced formula delimiters or braces before approving.")
    services: Services = request.app.state.services
    passages = await run_in_threadpool(split_passages, body.pages)
    if not passages:
        raise HTTPException(422, "Add readable course text before approving these pages.")
    from uuid import uuid4

    concepts: dict[str, list[int]] = {}
    for passage in passages:
        passage.concepts = skills_in(passage.text, registry)
        for concept in passage.concepts:
            concepts.setdefault(concept, [])
            if passage.page not in concepts[concept]:
                concepts[concept].append(passage.page)
    rows = [
        {
            "passage_id": uuid4(),
            "user_id": user_id,
            "doc_id": doc_id,
            "page": p.page,
            "position": p.position,
            "text": p.text,
            "concepts": p.concepts,
        }
        for p in passages
    ]
    async with services.engine.begin() as conn:
        await user_scope(conn, user_id)
        doc = (
            await conn.execute(
                select(*(c for c in t.documents.c if c.name != "source_pdf"))
                .where(t.documents.c.doc_id == doc_id, t.documents.c.user_id == user_id)
                .with_for_update()
            )
        ).one_or_none()
        if doc is None:
            raise HTTPException(404, "No such document")
        if len(body.pages) != doc.pages:
            raise HTTPException(422, "Keep the original page count so citations stay correct.")
        extraction = {**(doc.extraction or {}), "pages": body.pages, "reviewed": True}
        await conn.execute(
            delete(t.document_passages).where(
                t.document_passages.c.doc_id == doc_id, t.document_passages.c.user_id == user_id
            )
        )
        await conn.execute(insert(t.document_passages), rows)
        await conn.execute(
            update(t.documents)
            .where(t.documents.c.doc_id == doc_id)
            .values(
                extraction=extraction,
                review_required=False,
                status="ready",
                indexed=False,
                passages=len(rows),
                concepts=concepts,
            )
        )
        await append_event(
            conn,
            LibraryChanged(
                user_id=user_id,
                ts=datetime.now(UTC),
                payload=LibraryPayload(action="document_reviewed", doc_id=doc_id),
            ),
        )
    indexed = False
    if services.memory:
        try:
            await services.memory.delete_document(user_id, doc_id)
            await services.memory.write_passages(user_id, doc_id, doc.title, rows)
            indexed = True
        except Exception:
            pass  # Postgres holds the reviewed source even if the search service is offline.
    async with services.engine.begin() as conn:
        await user_scope(conn, user_id)
        row = (
            await conn.execute(
                update(t.documents)
                .where(t.documents.c.doc_id == doc_id, t.documents.c.user_id == user_id)
                .values(indexed=indexed)
                .returning(*(c for c in t.documents.c if c.name != "source_pdf"))
            )
        ).one()
    return library._view(row)


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: UUID, request: Request, user_id: CurrentUser) -> None:
    services: Services = request.app.state.services
    if not await library.remove(services.engine, services.memory, user_id, doc_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such document")
