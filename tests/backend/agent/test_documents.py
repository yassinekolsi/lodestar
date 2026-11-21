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
from backend.documents.math_text import math_issues
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


def test_math_blocks_survive_chunking_and_bad_delimiters_need_review() -> None:
    formula = r"$$P(A\mid B)=\frac{P(A\cap B)}{P(B)}$$"
    code = '```cpp\n  cout << "hello";\n```'
    pages = ["A paragraph about a course. " * 18 + formula + "\n" + code + " more text" * 60]
    passages = ingest.split_passages(pages)
    assert any(formula in p.text for p in passages)
    assert any(code in p.text for p in passages)
    table = "| Event | Probability |\n| --- | --- |\n| A | $P(A)=0.5$ |"
    assert any(
        table in p.text for p in ingest.split_passages(["A paragraph. " * 48 + "\n" + table])
    )
    assert not math_issues(formula)
    assert math_issues(r"$$P(A)=1$")
    assert math_issues(r"$\left\{A, B\}$")


async def test_scanned_page_uses_gemini_twice_and_stays_out_of_study(monkeypatch) -> None:
    import io
    from unittest.mock import AsyncMock

    from pypdf import PdfWriter

    from backend.documents.ocr import Transcription, extract_document

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    factory = SimpleNamespace(
        gemini_pdf_page=AsyncMock(
            side_effect=[
                Transcription(text=r"$P(A)=\frac{1}{6}$", uncertainties=[]),
                Transcription(
                    text=r"$P(A)=\frac{1}{4}$ [unclear]", uncertainties=["Unclear denominator."]
                ),
            ]
        )
    )
    doc = await extract_document(buffer.getvalue(), "scan.pdf", load_registry(), factory, uuid4())
    assert factory.gemini_pdf_page.await_count == 2
    assert doc.review_required and doc.method == "gemini-3.5-flash-lite"
    assert doc.warnings["1"] and r"\frac{1}{4}" in doc.page_texts[0]


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
        url = f"/documents/{doc['doc_id']}"
        assert (await c.get(f"{url}/pages", headers=other)).status_code == 404
        assert (await c.get(f"{url}/original", headers=other)).status_code == 404
        assert (
            await c.put(f"{url}/review", json={"pages": [text]}, headers=other)
        ).status_code == 404
        for bad in ("[unclear]", r"$$P(A)=1$", text + "\f" + text):
            pages = bad.split("\f")
            assert (
                await c.put(f"{url}/review", json={"pages": pages}, headers=headers)
            ).status_code == 422
        async with aengine.begin() as conn:
            await conn.execute(
                t.documents.update()
                .where(t.documents.c.doc_id == UUID(doc["doc_id"]))
                .values(review_required=True, source_pdf=b"%PDF-private-source")
            )
        original = await c.get(f"{url}/original", headers=headers)
        assert original.content == b"%PDF-private-source"
        assert original.headers["cache-control"] == "no-store"
        async with aengine.connect() as conn:
            blocked, _ = await library.quiz_content(
                conn, user, load_registry(), 42, doc_id=UUID(doc["doc_id"])
            )
            assert blocked is None
        reviewed = await c.put(f"{url}/review", json={"pages": [text]}, headers=headers)
        assert reviewed.status_code == 200, reviewed.text
        assert not reviewed.json()["review_required"]
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
                "document_reviewed",
                "document_deleted",
            }


async def test_gemini_factory_requires_consent_and_hides_invalid_provider_data(
    aengine, monkeypatch
):
    import base64
    import json

    from backend.db.llm_store import save_credential
    from backend.documents.ocr import Transcription
    from backend.llm.factory import LlmFactory
    from tests.backend.agent.conftest import grant, new_user, test_settings
    from tests.backend.llm import fake_provider as provider_module

    user = await new_user(aengine)
    secret = "private-gemini-canary-12345678"
    with provider_module.fake_provider() as fake:
        factory = LlmFactory(
            load_registry(), test_settings(), aengine, base_overrides={"gemini": fake.base}
        )
        async with aengine.begin() as conn:
            await save_credential(
                conn, user, "gemini", factory.vault.seal(user, "gemini", secret), "ok"
            )
        with pytest.raises(ValueError, match="Enable Cloud AI"):
            await factory.gemini_pdf_page(user, b"source", "Transcribe", Transcription)
        assert fake.requests == []
        await grant(aengine, user, "cloud_ai")

        def response(text):
            return {
                "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": text}]}}]
            }

        monkeypatch.setattr(
            provider_module,
            "_route",
            lambda *_: (200, response(json.dumps({"text": secret, "uncertainties": "invalid"}))),
        )
        with pytest.raises(ValueError) as error:
            await factory.gemini_pdf_page(user, b"source", "Transcribe", Transcription)
        assert secret not in str(error.value)
        assert str(error.value) == "Gemini could not read this page. Try again later."
        monkeypatch.setattr(
            provider_module,
            "_route",
            lambda *_: (200, response(json.dumps({"text": "$P(A)=1$", "uncertainties": []}))),
        )
        result = await factory.gemini_pdf_page(user, b"source", "Transcribe", Transcription)
        assert result.text == "$P(A)=1$"
        request = fake.requests[-1]
        assert "gemini-3.5-flash-lite" in request.path and "key=" not in request.path
        assert request.headers["x-goog-api-key"] == secret
        assert secret not in json.dumps(request.body)
        assert request.body["contents"][0]["parts"][1]["inline_data"] == {
            "mime_type": "application/pdf",
            "data": base64.b64encode(b"source").decode(),
        }
