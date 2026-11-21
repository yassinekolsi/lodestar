"""French and Tunisian Arabic (Derja), backend/i18n.py: the locale of a request, the course in
French, routing what students type in each language, the explain-it-back rubric and the coach's
checks on a reply that isn't in English."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from backend import i18n
from backend.agent import learning
from backend.agent.intents import classify
from backend.coach.verify import sentences, verify
from backend.contracts.facts import Fact, FactsPacket
from backend.registry.loader import load_registry

REGISTRY = load_registry()
HERE = Path(__file__).parent
LABELLED: list[dict[str, Any]] = yaml.safe_load(
    (HERE / "agent" / "intents_fr_tn.yaml").read_text(encoding="utf-8")
)


@pytest.fixture(autouse=True)
def english_after() -> Iterator[None]:
    yield
    i18n.set_current("en")


# The locale of a request ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "want"),
    [
        ("fr", "fr"),
        ("fr-FR,fr;q=0.9", "fr"),
        ("tn", "tn"),
        ("ar-TN", "tn"),
        ("ar", "tn"),
        ("en-GB", "en"),
        ("de", "en"),
        ("", "en"),
        (None, "en"),
    ],
)
def test_parse(value: str | None, want: str) -> None:
    assert i18n.parse(value) == want


def test_derja_studies_from_french_notes() -> None:
    assert i18n.course_locale("tn") == "fr"
    assert i18n.course_locale("fr") == "fr"
    assert i18n.course_locale("en") == "en"


def test_middleware_reads_the_header_and_the_websocket_query() -> None:
    app = FastAPI()
    app.add_middleware(i18n.LocaleMiddleware)

    @app.get("/lang")
    def lang() -> dict[str, str]:  # sync: runs in a worker thread, which keeps the context
        return {"locale": i18n.current()}

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await socket.accept()
        await socket.send_text(i18n.current())
        await socket.close()

    client = TestClient(app)
    assert client.get("/lang").json() == {"locale": "en"}
    assert client.get("/lang", headers={"X-Lodestar-Locale": "fr"}).json() == {"locale": "fr"}
    assert client.get("/lang", headers={"X-Lodestar-Locale": "tn"}).json() == {"locale": "tn"}
    with client.websocket_connect("/ws?lang=tn") as socket:
        assert socket.receive_text() == "tn"
    assert i18n.current() == "en"  # nothing leaks out of a request


def test_the_model_is_told_the_language() -> None:
    assert i18n.with_language("rules") == "rules"
    assert "French" in i18n.with_language("rules", "fr")
    derja = i18n.with_language("rules", "tn")
    assert "Derja" in derja and "Arabic script" in derja and "decimal points" in derja


# The course in French -------------------------------------------------------------------------


def test_every_concept_question_and_section_is_translated() -> None:
    english = REGISTRY.courses[0]
    [french] = REGISTRY.translations["fr"]
    assert french.name == "Probabilités 1"
    for en, fr in zip(english.sections, french.sections, strict=True):
        assert fr.title != en.title and fr.text != en.text, en.id
    for en_c, fr_c in zip(english.concepts, french.concepts, strict=True):
        assert fr_c.name != en_c.name, en_c.id
        assert fr_c.key_ideas != en_c.key_ideas, en_c.id
        for en_m, fr_m in zip(en_c.misconceptions, fr_c.misconceptions, strict=True):
            assert fr_m.fix != en_m.fix, f"{en_c.id}/{en_m.id}"
        for en_q, fr_q in zip(en_c.questions, fr_c.questions, strict=True):
            assert fr_q.stem != en_q.stem, en_q.id
            # The answer, its level and every misconception tag are the course's own.
            assert fr_q.answer == en_q.answer and fr_q.level == en_q.level, en_q.id
            assert [o.misconception for o in fr_q.options] == [
                o.misconception for o in en_q.options
            ], en_q.id


def test_the_registry_answers_in_the_language_of_the_request() -> None:
    assert REGISTRY.course.concept("bayes").name == "Bayes' theorem"
    i18n.set_current("fr")
    assert REGISTRY.course.concept("bayes").name == "Théorème de Bayes"
    assert REGISTRY.localized().dimension("bayes").name == "Théorème de Bayes"
    i18n.set_current("tn")  # Derja: the course stays in French
    assert REGISTRY.course.concept("bayes").name == "Théorème de Bayes"
    assert REGISTRY.course_of("bayes") is not None


def test_a_quiz_in_french_keeps_the_same_answers() -> None:
    en = learning.quiz_content(REGISTRY.course, "conditional", 0.5, seed=7, seen=set())
    i18n.set_current("fr")
    fr = learning.quiz_content(REGISTRY.course, "conditional", 0.5, seed=7, seen=set())
    assert [q["id"] for q in fr["questions"]] == [q["id"] for q in en["questions"]]
    assert [q["answer"] for q in fr["questions"]] == [q["answer"] for q in en["questions"]]
    assert fr["questions"][0]["stem"] != en["questions"][0]["stem"]
    assert fr["questions"][0]["hints"][1] == "Deux des mauvaises réponses ont disparu."


# Routing --------------------------------------------------------------------------------------


def test_french_and_derja_utterances_route_like_english() -> None:
    assert len(LABELLED) >= 45
    wrong = []
    for item in LABELLED:
        intent = classify(item["text"], "ui", REGISTRY).intent
        checks = {
            "kind": (intent.kind, item["kind"]),
            "game": (intent.game_id, item.get("game", intent.game_id)),
            "dim": (intent.dim, item.get("dim", intent.dim)),
            "avoid": (sorted(intent.avoid_dims), sorted(item.get("avoid", []))),
        }
        if item["kind"] == "play":
            checks["quick"] = (intent.quick, item.get("quick", False))
        if item["kind"] == "chat":
            checks["tool"] = (intent.tool, item.get("tool"))
        bad = {k: got for k, (got, want) in checks.items() if got != want}
        if bad:
            wrong.append((item["text"], bad))
    assert wrong == []


# The explain-it-back rubric -------------------------------------------------------------------


def test_words_ignore_accents_and_keep_arabic_script() -> None:
    assert learning.words_of("Réunion, réunion et REUNION") == [
        "reunion",
        "reunion",
        "et",
        "reunion",
    ]
    assert learning.words_of("الاحتمال الشرطي P(A|B)") == ["الاحتمال", "الشرطي", "p", "a", "b"]


def test_a_french_explanation_scores_against_the_french_key_ideas() -> None:
    i18n.set_current("fr")
    content = learning.explain_content(REGISTRY.course, "conditional", 0.3)
    assert content["prompt"].startswith("Explique « Probabilité conditionnelle »")
    answer = (
        "Savoir que B s'est produit reduit l'univers a B. On divise la probabilite des deux par "
        "la probabilite de B, donc le denominateur est P(B) et pas tout l'univers. Attention, "
        "P(A | B) n'est pas la meme chose que P(B | A) : par exemple éternuer et être enrhumé."
    )
    score, hits = learning.rubric_score(answer, content["key_ideas"])
    assert all(hits), hits
    assert score > 0.9


# The coach's checks on a translated reply -----------------------------------------------------


def _packet() -> FactsPacket:
    return FactsPacket(facts=[Fact(id="F1", text="Conditional probability mastery 45% (31-58%)")])


def test_arabic_question_marks_end_sentences() -> None:
    assert len(sentences("المستوى متاعك 45% [F1]. تحب خمسة أسئلة ؟ يلّا")) == 3


def test_numbers_in_a_french_or_derja_reply_must_be_cited() -> None:
    i18n.set_current("fr")
    reply = "Ta maîtrise est de 45% (entre 31 et 58%) [F1]. Tu veux cinq questions ?"
    ok = verify(reply, _packet())
    assert ok.ok, ok.violations
    bad = verify("Ta maîtrise est de 70%.", _packet())
    assert not bad.ok
    i18n.set_current("tn")
    assert verify("المستوى متاعك 45% [F1]. تحب أسئلة ؟", _packet()).ok
    assert not verify("باش توصل 90% أكيد.", _packet()).ok


def test_a_promise_in_french_is_refused_unless_denied() -> None:
    i18n.set_current("fr")
    assert not verify("Tu vas certainement réussir.", _packet()).ok
    assert verify("Personne ne peut le dire certainement.", _packet()).ok
