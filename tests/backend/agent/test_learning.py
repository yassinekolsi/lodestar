"""The study-coach logic (docs/plan/19): quizzes from the course, misconceptions, prerequisite gaps,
explain-it-back and review timing. Pure functions, no database."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.agent import learning
from backend.agent.intents import classify
from backend.contracts.trial import TrialEvent
from backend.registry.course import Course
from backend.registry.loader import load_registry
from backend.scoring.kalman_elo import Belief
from backend.scoring.norms import Norms
from backend.scoring.quality import TrialSample, assess_quality
from backend.scoring.rounds import observed_score

REGISTRY = load_registry()
COURSE = REGISTRY.course
NORMS = Norms()


def test_every_concept_is_a_skill_with_a_quiz_and_an_explain_it_back() -> None:
    dims = {d.id for d in REGISTRY.dimensions}
    for c in COURSE.concepts:
        assert c.id in dims
        quiz = REGISTRY.game(f"quiz_{c.id}")
        explain = REGISTRY.game(f"explain_{c.id}")
        assert quiz.plugin_id == "quiz" and quiz.dims == {c.id: 1.0}
        assert explain.plugin_id == "explain" and explain.scoring == "rubric"
        assert quiz.chance == 0.25  # four options


def test_every_question_has_one_answer_and_known_misconceptions() -> None:
    for c in COURSE.concepts:
        known = {m.id for m in c.misconceptions}
        for q in c.questions:
            assert sum(o.correct for o in q.options) == 1
            assert {o.misconception for o in q.options if o.misconception} <= known
            assert 0 <= q.level <= 1 and q.explain


def _course_dict() -> dict[str, Any]:
    return COURSE.model_dump(mode="json")


def test_a_prerequisite_must_come_earlier_so_there_are_no_cycles() -> None:
    data = _course_dict()
    data["concepts"][0]["requires"] = ["bayes"]  # sample spaces can't build on Bayes
    with pytest.raises(ValidationError, match="must be an earlier concept"):
        Course.model_validate(data)


def test_a_question_with_two_right_answers_is_rejected() -> None:
    data = _course_dict()
    data["concepts"][0]["questions"][0]["options"][1]["correct"] = True
    with pytest.raises(ValidationError, match="exactly one option"):
        Course.model_validate(data)


def test_a_quiz_serves_questions_near_the_level_easiest_first_with_the_answer_kept() -> None:
    content = learning.quiz_content(COURSE, "conditional", 0.6, seed=3, seen=set())
    questions = content["questions"]
    assert len(questions) == learning.QUESTIONS_PER_QUIZ
    assert [q["level"] for q in questions] == sorted(q["level"] for q in questions)
    for q in questions:
        _, original = COURSE.find_question(q["id"]) or (None, None)
        assert original is not None
        right = next(o.text for o in original.options if o.correct)
        assert q["options"][q["answer"]]["text"] == right  # shuffled, answer still right
        assert q["answer"] not in q["remove"] and len(q["remove"]) == 2
        for o in q["options"]:
            if o["misconception"]:
                assert o["misconception"] in q["fixes"]


def test_a_quiz_prefers_questions_not_seen_this_week() -> None:
    first = learning.quiz_content(COURSE, "bayes", 0.5, seed=1, seen=set())
    seen = {q["id"] for q in first["questions"][:3]}
    again = learning.pick_questions(COURSE.concept("bayes"), 0.5, seen)
    fresh = [q.id for q in again if q.id not in seen]
    assert len(fresh) == len(COURSE.concept("bayes").questions) - len(seen)


def test_the_rubric_finds_the_key_ideas_and_scales_down_short_answers() -> None:
    content = learning.explain_content(COURSE, "conditional", 0.3)
    full = (
        "Conditional probability is the probability of A once you know B happened. Knowing B "
        "shrinks the sample space to B, so P(A | B) = P(A and B) divided by P(B). The denominator "
        "is P(B), not the whole sample space, and P(A | B) is not the same as P(B | A)."
    )
    score, hits = learning.rubric_score(full, content["key_ideas"])
    assert all(hits) and score == pytest.approx(1.0)
    short, _ = learning.rubric_score("P(A and B) divided by P(B)", content["key_ideas"])
    assert short < 0.3


def _belief(percent: float, n: int = 40, sigma: float = 0.3) -> Belief:
    """A belief whose mastery is `percent`."""
    import math

    p = percent / 100
    return Belief(mu=math.log(p / (1 - p)), sigma=sigma, n=n)


def test_a_gap_goes_back_to_the_shaky_prerequisite_of_a_struggling_concept() -> None:
    beliefs = {
        "sample_space": _belief(85), "counting": _belief(75), "equally_likely": _belief(80),
        "conditional": _belief(42), "total_probability": _belief(75), "bayes": _belief(12),
    }  # fmt: skip
    gap = learning.find_gap(COURSE, beliefs, {}, NORMS)
    assert gap is not None
    assert (gap.concept, gap.prereq, gap.chain) == ("bayes", "conditional", ["bayes", "conditional"])
    reason = learning.gap_reason(COURSE, gap, asked=False)
    assert "Bayes' theorem is at 12%" in reason and "conditional probability" in reason


def test_a_gap_follows_the_chain_down_to_the_deepest_shaky_concept() -> None:
    beliefs = {
        "sample_space": _belief(40), "counting": _belief(75), "equally_likely": _belief(80),
        "conditional": _belief(42), "total_probability": _belief(75), "bayes": _belief(12),
    }  # fmt: skip
    gap = learning.find_gap(COURSE, beliefs, {}, NORMS)
    assert gap is not None and gap.chain == ["bayes", "conditional", "sample_space"]


def test_no_gap_when_the_prerequisites_are_solid() -> None:
    beliefs = {d: _belief(85) for d in COURSE.ancestors("bayes")} | {"bayes": _belief(12)}
    assert learning.find_gap(COURSE, beliefs, {}, NORMS) is None


def test_a_prerequisite_never_checked_counts_as_the_gap() -> None:
    beliefs = {"random_variables": _belief(80), "expectation": _belief(20)}
    gap = learning.find_gap(COURSE, beliefs, {}, NORMS, concept="binomial")
    assert gap is not None and gap.prereq_pct is None


def test_struggling_is_about_mastery_not_the_share_of_right_answers() -> None:
    beliefs = {"bayes": _belief(20), "counting": _belief(80)}
    # Mostly right answers on easy questions don't hide a low mastery.
    assert learning.struggling(COURSE, beliefs, NORMS) == ["bayes"]


def test_review_comes_sooner_for_concepts_known_less_well() -> None:
    now = datetime.now(UTC)
    weak = _belief(55)
    strong = _belief(90)
    three_days = now - timedelta(days=3)
    weak = Belief(weak.mu, weak.sigma, weak.n, three_days)
    strong = Belief(strong.mu, strong.sigma, strong.n, three_days)
    assert learning.review_due(weak, NORMS.percentile("x", weak), now)
    assert not learning.review_due(strong, NORMS.percentile("x", strong), now)


def _trial(correct: bool, hints: int = 0, rt: float = 20_000, level: float = 0.5) -> TrialEvent:
    return TrialEvent(
        trial_id=uuid4(), round_id=uuid4(), session_id=uuid4(), game_id="quiz_bayes",
        level=level, trial_index=0, stimulus={"question_id": "by1"}, correct=correct,
        rt_ms=rt, hint_level=hints, ts=datetime.now(UTC),
    )  # fmt: skip


def test_an_answer_found_with_hints_counts_for_less() -> None:
    game = REGISTRY.game("quiz_bayes")
    assert observed_score(game, _trial(True)) == 1.0
    assert observed_score(game, _trial(True, hints=1)) == 0.75
    assert observed_score(game, _trial(True, hints=2)) == 0.5
    assert observed_score(game, _trial(False, hints=2)) == 0.0


def test_clicking_through_a_quiz_is_flagged_but_reading_it_is_not() -> None:
    game = REGISTRY.game("quiz_bayes")
    mashed = [TrialSample(i % 3 == 0, 900.0) for i in range(5)]
    read = [TrialSample(i % 3 == 0, 18_000.0) for i in range(5)]
    flagged = assess_quality(mashed, chance=game.chance, rushed_ms=game.rushed_ms)
    honest = assess_quality(read, chance=game.chance, rushed_ms=game.rushed_ms)
    assert flagged.verdict == "random_clicking" and flagged.trust == 0
    assert honest.trust == 1


def test_mastery_is_the_chance_of_a_typical_question_with_its_range() -> None:
    pct = NORMS.percentile("bayes", Belief(0.0, 0.5))
    assert pct.value == pytest.approx(50.0)
    assert pct.low < 50 < pct.high and pct.source == "mastery"


@pytest.mark.parametrize(
    ("said", "kind", "tool", "dim"),
    [
        ("I don't get Bayes' theorem", "chat", "teach", "bayes"),
        ("what is a random variable?", "chat", "teach", "random_variables"),
        ("What do I keep getting wrong?", "chat", "mistakes", None),
        ("Quiz me on conditional probability", "play", None, "conditional"),
        ("revise the binomial distribution", "play", None, "binomial"),
        ("why did you pick that?", "chat", "explain", None),
    ],
)
def test_students_words_reach_the_right_concept_and_tool(
    said: str, kind: str, tool: str | None, dim: str | None
) -> None:
    intent = classify(said, "ui", REGISTRY).intent
    assert (intent.kind, intent.tool, intent.dim) == (kind, tool, dim)
