"""A real student works from their own uploads; only the demo people study the built-in course
(backend/course_scope.py). The rest of the suite runs with LODESTAR_BUILT_IN_COURSE=all
(tests/conftest.py); these tests switch to the product's default, "demo"."""

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from backend import course_scope, i18n
from backend.config import get_settings
from backend.db import tables as t
from backend.documents import ingest, library
from backend.documents.questions import Source, from_text
from backend.registry.loader import load_registry
from tests.backend.agent.conftest import RunnerFactory, new_user
from tests.backend.agent.test_graph import collect

REGISTRY = load_registry()
FRENCH_PDF = Path("docs/demo/structures-de-donnees-piles-files.pdf")


@pytest.fixture(autouse=True)
def product_default(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    settings = get_settings().model_copy(update={"built_in_course": "demo"})
    monkeypatch.setattr(course_scope, "get_settings", lambda: settings)
    yield
    course_scope.set_enabled(True)
    i18n.set_current("en")


def said(events: list[dict[str, Any]]) -> str:
    return " ".join(e["text"] for e in events if e["kind"] == "say")


def exercise(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for e in events:
        if e["kind"] == "interrupt" and e["payload"].get("type") == "exercise":
            spec: dict[str, Any] = e["payload"]["spec"]
            return spec
    return None


async def name(engine: AsyncEngine, user_id: UUID, display_name: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            update(t.users).where(t.users.c.user_id == user_id).values(display_name=display_name)
        )


# Who studies what ------------------------------------------------------------------------------


def test_only_the_demo_people_are_demo() -> None:
    assert course_scope.is_demo("Alex")
    assert course_scope.is_demo("Classmate 07")
    assert not course_scope.is_demo(None)
    assert not course_scope.is_demo("")
    assert not course_scope.is_demo("Alexandra")


def test_without_the_built_in_course_the_registry_has_none() -> None:
    assert REGISTRY.active_course is not None
    course_scope.set_enabled(False)
    assert REGISTRY.active_course is None
    assert REGISTRY.courses_in() == []
    assert REGISTRY.course_of("bayes") is None
    assert REGISTRY.localized("fr").dimension("bayes").name == "Bayes' theorem"  # no course names


# A real student's session --------------------------------------------------------------------


async def test_a_new_student_is_asked_for_a_chapter_not_given_the_demo_course(
    make_runner: RunnerFactory, aengine: AsyncEngine
) -> None:
    runner = await make_runner()
    user_id = await new_user(aengine)
    session_id = await runner.create_session(user_id, "ui")
    events = await collect(runner, user_id, session_id)  # "Start studying"
    assert exercise(events) is None
    assert "upload a PDF" in said(events)
    # Asking about a concept of the demo course answers from their documents, which they lack.
    session_id = await runner.create_session(user_id, "ui")
    events = await collect(runner, user_id, session_id, message="I don't get Bayes' theorem")
    assert "Upload the chapter in Documents" in said(events)
    assert not [e for e in events if e.get("card") == "lesson"]  # no built-in notes


async def test_an_upload_waiting_for_review_is_not_used_yet(
    make_runner: RunnerFactory, aengine: AsyncEngine
) -> None:
    runner = await make_runner()
    user_id = await new_user(aengine)
    await library.start(aengine, user_id, "chapter.pdf", 2, None, "", None)
    session_id = await runner.create_session(user_id, "ui")
    events = await collect(runner, user_id, session_id)
    assert exercise(events) is None
    assert "press Validate" in said(events)


async def test_studying_a_french_chapter_in_french_and_derja(
    make_runner: RunnerFactory, aengine: AsyncEngine
) -> None:
    runner = await make_runner()
    user_id = await new_user(aengine)
    data = await asyncio.to_thread(FRENCH_PDF.read_bytes)
    doc = await asyncio.to_thread(ingest.extract, data, FRENCH_PDF.name, REGISTRY)
    await library.save(aengine, None, user_id, FRENCH_PDF.name, doc)

    i18n.set_current("fr")
    session_id = await runner.create_session(user_id, "ui")
    spec = exercise(await collect(runner, user_id, session_id))  # "Start studying"
    assert spec is not None and spec["game_id"] == "quiz_notes"
    questions = spec["content"]["questions"]
    assert len(questions) >= 3
    assert all("ton document (page" in q["stem"] for q in questions)
    assert all(not o["text"].lower().startswith("l'") for q in questions for o in q["options"])

    i18n.set_current("tn")
    session_id = await runner.create_session(user_id, "ui")
    spec = exercise(await collect(runner, user_id, session_id, message="اختبرني على الnotes متاعي"))
    assert spec is not None and spec["game_id"] == "quiz_notes"
    # The course is taught in French: French questions, Derja hints.
    assert "ton document" in spec["content"]["questions"][0]["stem"]
    assert "الdocument متاعك" in spec["content"]["questions"][0]["hints"][0]


async def test_the_demo_person_keeps_the_built_in_course(
    make_runner: RunnerFactory, aengine: AsyncEngine
) -> None:
    runner = await make_runner()
    user_id = await new_user(aengine)
    await name(aengine, user_id, "Alex")
    session_id = await runner.create_session(user_id, "ui")
    spec = exercise(await collect(runner, user_id, session_id))
    assert spec is not None and spec["game_id"] != "quiz_notes"
    assert REGISTRY.concept_for_game(spec["game_id"]) is not None


# Questions from a French document --------------------------------------------------------------


def test_questions_from_a_french_page_are_worded_in_french() -> None:
    i18n.set_current("fr")
    text = (
        "Une pile est une structure de données où le dernier élément ajouté est le premier retiré. "
        "L'empilement est l'opération qui ajoute un élément au sommet de la pile. "
        "Le dépilement est l'opération qui retire l'élément situé au sommet de la pile. "
        "Une file est une structure de données où le premier élément ajouté est le premier "
        "retiré. Le sommet désigne le dernier élément ajouté, le seul auquel on accède."
    )
    questions = from_text([Source(text=text, page=3)], [], seed=1)
    assert questions
    assert questions[0]["stem"].startswith(("Quel terme ton document (page 3)", "Complète le trou"))
    assert questions[0]["hints"][0] == "C'est à la page 3 de ton document."
    options = {o["text"] for q in questions for o in q["options"]}
    assert "empilement" in options and "L'empilement" not in options
