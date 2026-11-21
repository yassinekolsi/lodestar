"""What makes Lodestar a study coach (docs/plan/19): course exercises, misconceptions, prerequisite
gaps and review timing. Pure functions plus two read-only queries; code decides, as everywhere.

- A quiz serves questions near the level the scorer chose, ramping up, avoiding repeats.
- Every wrong option a student picks that matches a known misconception is counted, so the coach
  can say *how* an answer was wrong and point to the fix the team wrote.
- A prerequisite gap: a concept keeps going wrong and a concept it builds on is still shaky or was
  never checked. Lodestar goes back to the deepest shaky prerequisite first and says why.
"""

import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from backend.db import tables as t
from backend.registry.course import Concept, Course, Question
from backend.registry.models import Registry
from backend.scoring.kalman_elo import Belief
from backend.scoring.norms import Norms, PercentRange

QUESTIONS_PER_QUIZ = 5
# A concept counts as shaky below this mastery, or when its range is this wide.
SHAKY_PERCENT = 60.0
UNSURE_WIDTH = 45.0
# A concept is struggling below this mastery, when Lodestar is fairly sure of it: the top of its
# 80% range is under STRUGGLING_HIGH, so one unlucky quiz doesn't send a student back a chapter
# (experiment 13, simulator/gap_eval.py).
STRUGGLING_PERCENT = 45.0
STRUGGLING_HIGH = 50.0
RECENT_DAYS = 14

_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "each", "every", "for", "from", "has", "in",
    "is", "it", "its", "not", "of", "on", "or", "same", "than", "that", "the", "then", "this",
    "to", "with", "when", "what", "you", "your", "only", "all", "into", "can", "does", "doesn",
    "don", "t", "s", "up", "one", "two",
}  # fmt: skip


# Exercises ------------------------------------------------------------------------------------


def _section(course: Course, concept: Concept) -> dict[str, str]:
    section = course.section(concept.section)
    return {"id": section.id, "title": section.title}


def pick_questions(
    concept: Concept, level: float, seen: set[str], n: int = QUESTIONS_PER_QUIZ
) -> list[Question]:
    """The n questions nearest the level, fresh ones first, served easiest first."""
    ranked = sorted(concept.questions, key=lambda q: (q.id in seen, abs(q.level - level)))
    return sorted(ranked[:n], key=lambda q: q.level)


def quiz_content(
    course: Course, concept_id: str, level: float, seed: int, seen: set[str]
) -> dict[str, Any]:
    """What the quiz plugin plays: questions with shuffled options, the answer, the explanation,
    two hints, and the fix for every misconception a wrong option carries."""
    concept = course.concept(concept_id)
    rng = random.Random(seed)
    section = _section(course, concept)
    questions = []
    for q in pick_questions(concept, level, seen):
        order = list(range(len(q.options)))
        rng.shuffle(order)
        options = [q.options[i] for i in order]
        answer = next(i for i, o in enumerate(options) if o.correct)
        # Hint 2 takes away two wrong answers, keeping one a misconception would pick if any.
        wrong = [i for i, o in enumerate(options) if not o.correct]
        tagged = [i for i in wrong if options[i].misconception]
        keep = tagged[0] if tagged else wrong[0]
        removed = [i for i in wrong if i != keep][:2]
        fixes = {}
        for o in options:
            if o.misconception and (m := concept.misconception(o.misconception)):
                fixes[m.id] = {"text": m.text, "fix": m.fix}
        questions.append(
            {
                "id": q.id,
                "level": q.level,
                "stem": q.stem,
                "options": [{"text": o.text, "misconception": o.misconception} for o in options],
                "answer": answer,
                "explain": q.explain,
                "hints": [
                    f"Notes {section['id']}, {section['title']}: {concept.key_ideas[0]}.",
                    "Two of the wrong answers are gone.",
                ],
                "remove": removed,
                "fixes": fixes,
            }
        )
    return {
        "course": course.id,
        "concept": concept.id,
        "concept_name": concept.name,
        "section": section,
        "questions": questions,
    }


def idea_words(idea: str) -> list[str]:
    """The words that show a key idea was mentioned (first 5 letters, so "multiply" matches
    "multiplying")."""
    words = re.findall(r"[a-z]+", idea.lower())
    return sorted({w[:5] for w in words if w not in _STOP and len(w) > 1})


def explain_content(course: Course, concept_id: str, level: float) -> dict[str, Any]:
    """Explain it back: the prompt and the key ideas the rubric looks for."""
    concept = course.concept(concept_id)
    audience = "a classmate who missed the lecture" if level < 0.5 else "a friend who has an exam"
    return {
        "course": course.id,
        "concept": concept.id,
        "concept_name": concept.name,
        "section": _section(course, concept),
        "prompt": (
            f"Explain {concept.name[0].lower()}{concept.name[1:]} to {audience}, in your own "
            "words. A few sentences and one example is enough."
        ),
        "key_ideas": [{"text": idea, "words": idea_words(idea)} for idea in concept.key_ideas],
    }


def rubric_score(text: str, key_ideas: Sequence[Mapping[str, Any]]) -> tuple[float, list[bool]]:
    """Share of key ideas mentioned (an idea counts when half its words appear), scaled down for
    very short answers. The same rule runs in the browser (frontend/src/games/explain)."""
    found = {w[:5] for w in re.findall(r"[a-z]+", text.lower())}
    hits = []
    for idea in key_ideas:
        words = list(idea["words"])
        need = max(1, (len(words) + 1) // 2)
        hits.append(sum(w in found for w in words) >= need)
    share = sum(hits) / len(hits) if hits else 0.0
    length = len(re.findall(r"\w+", text))
    return share * min(1.0, length / 25), hits


# Misconceptions -------------------------------------------------------------------------------


@dataclass(frozen=True)
class MisconceptionCount:
    concept: str
    concept_name: str
    id: str
    text: str
    fix: str
    count: int
    last_seen: datetime
    confident: int = 0  # picked while saying "fairly sure" or "sure"


async def misconception_counts(
    conn: AsyncConnection,
    registry: Registry,
    user_id: UUID | None = None,
    since: datetime | None = None,
) -> list[MisconceptionCount]:
    """Misconceptions picked in quizzes, most frequent first. Without a user: a whole class."""
    tag = t.trials.c.response["misconception"].astext
    concept = t.trials.c.stimulus["concept"].astext
    q = (
        select(
            concept.label("concept"),
            tag.label("tag"),
            func.count(),
            func.max(t.trials.c.ts),
            func.count().filter(t.trials.c.confidence >= 0.75),
        )
        .where(t.trials.c.game_id.like("quiz_%"), tag.is_not(None), t.trials.c.correct.is_(False))
        .group_by(concept, tag)
    )
    if user_id is not None:
        q = q.where(t.trials.c.user_id == user_id)
    if since is not None:
        q = q.where(t.trials.c.ts >= since)
    out = []
    for c_id, tag_id, n, last, sure in (await conn.execute(q)).all():
        course = registry.course_of(c_id)
        if course is None:
            continue
        c = course.concept(c_id)
        m = c.misconception(tag_id)
        if m is not None:
            out.append(
                MisconceptionCount(c.id, c.name, m.id, m.text, m.fix, int(n), last, int(sure))
            )
    return sorted(out, key=lambda m: (-m.count, -m.last_seen.timestamp()))


async def recent_answers(
    conn: AsyncConnection, registry: Registry, user_id: UUID, now: datetime
) -> dict[str, tuple[int, int]]:
    """Per concept: (right, total) over the last two weeks of quiz answers."""
    rows = await conn.execute(
        select(t.trials.c.game_id, t.trials.c.correct, func.count())
        .where(
            t.trials.c.user_id == user_id,
            t.trials.c.game_id.like("quiz_%"),
            t.trials.c.practice.is_(False),
            t.trials.c.correct.is_not(None),
            t.trials.c.ts >= now - timedelta(days=RECENT_DAYS),
        )
        .group_by(t.trials.c.game_id, t.trials.c.correct)
    )
    out: dict[str, tuple[int, int]] = {}
    for game_id, correct, n in rows.all():
        concept = registry.concept_for_game(game_id)
        if concept is None:
            continue
        right, total = out.get(concept, (0, 0))
        out[concept] = (right + (int(n) if correct else 0), total + int(n))
    return out


async def seen_questions(conn: AsyncConnection, user_id: UUID, game_id: str) -> set[str]:
    """Questions of this quiz the user answered in the last week."""
    rows = await conn.execute(
        select(t.trials.c.stimulus["question_id"].astext).where(
            t.trials.c.user_id == user_id,
            t.trials.c.game_id == game_id,
            t.trials.c.ts >= datetime.now(UTC) - timedelta(days=7),
        )
    )
    return {r[0] for r in rows.all() if r[0]}


# Prerequisite gaps ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Gap:
    """`concept` keeps going wrong; `prereq` is what to fix first; `chain` links them."""

    concept: str
    prereq: str
    chain: list[str]
    concept_pct: PercentRange
    prereq_pct: PercentRange | None  # None: never checked
    right: int
    total: int


def _shaky(belief: Belief | None, norms: Norms, dim: str) -> bool:
    if belief is None or belief.n == 0:
        return True
    pct = norms.percentile(dim, belief)
    return pct.value < SHAKY_PERCENT or pct.high - pct.low > UNSURE_WIDTH


def struggling(course: Course, beliefs: Mapping[str, Belief], norms: Norms) -> list[str]:
    """Concepts with low mastery, worst first. Mastery, not the share of right answers: the level
    adapts, so even a struggling student gets most of their (easier) questions right."""
    out = []
    for c in course.concepts:
        b = beliefs.get(c.id)
        if b is None or b.n == 0:
            continue
        pct = norms.percentile(c.id, b)
        if pct.value < STRUGGLING_PERCENT and pct.high < STRUGGLING_HIGH:
            out.append(c.id)
    return sorted(out, key=lambda d: beliefs[d].mu)


def find_gap(
    course: Course,
    beliefs: Mapping[str, Belief],
    recent: Mapping[str, tuple[int, int]],
    norms: Norms,
    concept: str | None = None,
) -> Gap | None:
    """The deepest shaky prerequisite under a struggling concept (or under `concept`, when the
    student asked about one). None when every prerequisite is solid: then the concept itself is
    the thing to work on."""
    targets = [concept] if concept else struggling(course, beliefs, norms)
    for target in targets:
        chain = [target]
        current = target
        while True:
            shaky = [
                r for r in course.concept(current).requires if _shaky(beliefs.get(r), norms, r)
            ]
            if not shaky:
                break
            # The weakest direct prerequisite (never checked counts as weakest).
            current = min(shaky, key=lambda r: beliefs[r].mu if r in beliefs else -99.0)
            chain.append(current)
        if len(chain) > 1:
            prereq = chain[-1]
            b = beliefs.get(prereq)
            right, total = recent.get(target, (0, 0))
            return Gap(
                concept=target,
                prereq=prereq,
                chain=chain,
                concept_pct=norms.percentile(target, beliefs.get(target, Belief())),
                prereq_pct=norms.percentile(prereq, b) if b is not None and b.n > 0 else None,
                right=right,
                total=total,
            )
    return None


def _lower(name: str) -> str:
    return f"{name[0].lower()}{name[1:]}"


def gap_reason(course: Course, gap: Gap, asked: bool) -> str:
    concept = course.concept(gap.concept).name
    prereq = _lower(course.concept(gap.prereq).name)
    if asked:
        opening = f"{concept} builds on {prereq}"
    else:
        opening = f"{concept} is at {gap.concept_pct.label()}, and it builds on {prereq}"
    state = (
        "which I haven't checked yet"
        if gap.prereq_pct is None
        else f"which is still shaky: {gap.prereq_pct.label()}"
    )
    via = ""
    if len(gap.chain) > 2:
        via = f" (through {', '.join(_lower(course.concept(c).name) for c in gap.chain[1:-1])})"
    section = course.concept(gap.prereq).section
    return (
        f"{opening}{via}, {state}. When a concept won't stick, the gap is often in what it builds "
        f"on, so let's fix that first. Notes {section} if you want to read it before."
    )


# Review timing --------------------------------------------------------------------------------


def review_due_in_days(pct: PercentRange) -> int:
    """Spaced review: the better a concept is known, the longer before it needs another look."""
    if pct.value >= 85:
        return 10
    if pct.value >= 70:
        return 5
    if pct.value >= 50:
        return 2
    return 1


def review_due(belief: Belief, pct: PercentRange, now: datetime) -> bool:
    if belief.last_practised is None or belief.n == 0:
        return False
    days = (now - belief.last_practised).total_seconds() / 86_400
    return days >= review_due_in_days(pct)
