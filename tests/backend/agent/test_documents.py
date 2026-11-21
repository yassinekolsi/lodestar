"""Page citations, source checks and ownership across the student library."""

from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select

from backend.api.deps import engine_dep
from backend.api.main import create_app
from backend.db import tables as t
from backend.documents import ingest, library, questions
from backend.registry.loader import load_registry


def test_chunking_preserves_headings_pages_and_bounds() -> None:
    first = "Operator overloading\n\n" + "A vector stores items in order. " * 65
    second = "File handling\n" + "x" * 2100
    chunks = ingest.split_passages([first, second])
    assert len(chunks) > 5
    assert all(len(p.text) <= ingest.PASSAGE_CHARS for p in chunks)
    assert {p.page for p in chunks} == {1, 2}
    assert "Operator overloading\n" in chunks[0].text
    assert "File handling" not in " ".join(p.text for p in chunks if p.page == 1)
    assert (
        ingest.title_of("notes.pdf", None, ["A course title\nAn author name"]) == "A course title"
    )


def test_scans_do_not_accept_watermarks(monkeypatch: pytest.MonkeyPatch) -> None:
    class Reader:
        pages = (SimpleNamespace(extract_text=lambda: "CamScanner\n1"),)
        metadata = None

    monkeypatch.setattr(ingest, "PdfReader", lambda _: Reader())
    with pytest.raises(ingest.UnreadableDocument, match="Gemini OCR"):
        ingest.pages_of(b"fake PDF", "chapter.pdf")


def test_quiz_evidence_checks_all_passages_on_the_same_page() -> None:
    sources = [
        questions.Source("A stack is a collection where the last item added is removed first.", 1),
        questions.Source("A queue is a collection where the first item added is removed first.", 1),
    ]
    good = questions.DraftQuestion(
        page=1,
        stem="Which structure removes the last item first?",
        options=["stack", "queue", "tree", "graph"],
        answer=0,
        explain="A stack removes the most recently added item.",
        evidence=sources[0].text,
    )
    assert len(questions.checked(questions.DraftQuiz(questions=[good]), sources, 7)) == 1
    invented = good.model_copy(
        update={"evidence": "An invented quote that is absent from the page."}
    )
    assert not questions.checked(questions.DraftQuiz(questions=[invented]), sources, 7)
    wrong_page = good.model_copy(update={"page": 2})
    assert not questions.checked(questions.DraftQuiz(questions=[wrong_page]), sources, 7)


def test_offline_quiz_has_page_section_and_valid_answers() -> None:
    sources = [
        questions.Source(
            "A stack is a collection where the last item added is removed first. "
            "A queue is a collection where the first item added is removed first. "
            "A tree is a collection with parent and child relationships. "
            "A graph is a collection of vertices connected by edges.",
            3,
        )
    ]
    made = questions.from_text(sources, [], 42)
    assert len(made) >= 2
    content = questions.as_content(made, "Structures", str(uuid4()), "code")
    assert content["section"]["id"] == "p. 3"
    assert all(0 <= q["answer"] < len(q["options"]) == 4 for q in made)
    assert library.requested_document("Quiz me on my notes") is None
    selected = uuid4()
    assert library.requested_document(f"Quiz me on my notes [document:{selected}]") == selected


async def test_subject_upload_quiz_ownership_events_and_delete(aengine) -> None:
    app = create_app(with_lifespan=False)
    app.state.services = SimpleNamespace(engine=aengine, memory=None, llm=None)
    app.dependency_overrides[engine_dep] = lambda: aengine
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:

        async def signup():
            response = await c.post("/users", json={"age_confirmed": True})
            assert response.status_code == 201
            data = response.json()
            return UUID(data["user_id"]), {"Authorization": f"Bearer {data['token']}"}

        user, headers = await signup()
        _, other = await signup()
        response = await c.post("/subjects", json={"name": "C++"}, headers=headers)
        assert response.status_code == 201
        subject_id = response.json()["subject_id"]
        assert (await c.post("/subjects", json={"name": "c++"}, headers=headers)).status_code == 409
        assert (await c.post("/subjects", json={"name": "   "}, headers=headers)).status_code == 422
        assert (await c.get("/subjects", headers=other)).json() == []
        text = (
            "A stack is a collection where the last item added is removed first. "
            "A queue is a collection where the first item added is removed first. "
            "A tree is a collection with parent and child relationships. "
            "A graph is a collection of vertices connected by edges."
        )
        uploaded = await c.post(
            "/documents",
            headers=headers,
            files={"file": ("structures.txt", text)},
            data={"subject_id": subject_id, "chapter": "Chapter 2"},
        )
        assert uploaded.status_code == 201, uploaded.text
        doc = uploaded.json()
        assert doc["chapter"] == "Chapter 2" and not doc["searchable"]
        assert (await c.get("/documents", headers=other)).json() == []
        assert not (await c.get("/documents", headers=headers)).json()[0]["searchable"]
        stolen = await c.post(
            "/documents",
            headers=other,
            files={"file": ("structures.txt", text)},
            data={"subject_id": subject_id},
        )
        assert stolen.status_code == 422
        assert (await c.delete(f"/documents/{doc['doc_id']}", headers=other)).status_code == 404
        async with aengine.connect() as conn:
            content, loadings = await library.quiz_content(
                conn, user, load_registry(), 42, doc_id=UUID(doc["doc_id"])
            )
            assert content and content["concept"] == doc["doc_id"] and loadings == {}
            missing, _ = await library.quiz_content(conn, user, load_registry(), 42, doc_id=uuid4())
            assert missing is None
        assert (await c.delete(f"/documents/{doc['doc_id']}", headers=headers)).status_code == 204
        async with aengine.connect() as conn:
            events = (
                (
                    await conn.execute(
                        select(t.events.c.payload).where(
                            t.events.c.user_id == user, t.events.c.type == "library.changed"
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert {e["action"] for e in events} == {
                "subject_created",
                "document_uploaded",
                "document_deleted",
            }
