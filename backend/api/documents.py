"""The student's own course documents (docs/plan/20): upload a PDF or text file, list, search
with page citations, delete."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, UploadFile, status
from pydantic import Field

from backend.agent.context import Services
from backend.api.deps import Conn, CurrentUser, RegistryDep
from backend.contracts.common import Contract
from backend.documents import library
from backend.documents.ingest import MAX_BYTES, UnreadableDocument, extract

router = APIRouter(tags=["documents"])


class PassageView(Contract):
    doc_id: str
    title: str
    page: int
    text: str
    concepts: list[str] = Field(default_factory=list)
    score: float


@router.post("/documents", response_model=library.DocumentView, status_code=201)
async def upload(
    file: UploadFile, request: Request, user_id: CurrentUser, registry: RegistryDep
) -> library.DocumentView:
    services: Services = request.app.state.services
    data = await file.read(MAX_BYTES + 1)
    try:
        doc = extract(data, file.filename or "document.pdf", registry)
    except UnreadableDocument as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return await library.save(
        services.engine, services.memory, user_id, file.filename or "document.pdf", doc
    )


@router.get("/documents", response_model=list[library.DocumentView])
async def list_documents(conn: Conn, user_id: CurrentUser) -> list[library.DocumentView]:
    return await library.documents(conn, user_id)


@router.get("/documents/search", response_model=list[PassageView])
async def search(q: str, request: Request, user_id: CurrentUser) -> list[PassageView]:
    services: Services = request.app.state.services
    if services.memory is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Search is offline right now")
    hits = await services.memory.search_documents(user_id, q[:500], limit=5)
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
    ]


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: UUID, request: Request, user_id: CurrentUser) -> None:
    services: Services = request.app.state.services
    if not await library.remove(services.engine, services.memory, user_id, doc_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such document")
