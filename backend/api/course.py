"""GET /course: the concept map for the signed-in student. GET /class: the teacher's view of the
whole class, aggregates only (docs/plan/19)."""

from datetime import UTC, datetime, timedelta
from statistics import median

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import distinct, func, select

from backend import i18n
from backend.agent import learning
from backend.agent.nodes.play import formats_by_dim
from backend.agent.patterns import read_patterns
from backend.api.deps import Conn, CurrentUser, Engine, RegistryDep
from backend.contracts.course import (
    ClassConcept,
    ClassMistake,
    ClassView,
    ConceptState,
    ConceptStatus,
    CourseMapView,
    GapView,
    SectionView,
)
from backend.db import tables as t
from backend.db.twin_store import read_twin
from backend.scoring.kalman_elo import Belief, drift
from backend.scoring.norms import Norms

router = APIRouter(tags=["course"])
SOLID_PERCENT = 70.0
CLASS_MISTAKES = 6

# The teacher's suggestions, in the language of the request (backend/i18n.py).
_SUGGEST: dict[i18n.Locale, dict[str, str]] = {
    "en": {
        "revisit": "Revisit notes {section} ({name}): {n} of {total} students are below {below}%",
        "mixup": ', and "{text}" shows up in {n} students\' answers',
        "quiet": "{n} of {total} students haven't studied in the last 7 days. Lodestar offers "
        "them short, easy sessions when they come back.",
    },
    "fr": {
        "revisit": "Revoir les notes {section} ({name}) : {n} étudiants sur {total} sont sous "
        "{below}%",
        "mixup": ", et « {text} » revient dans les réponses de {n} étudiants",
        "quiet": "{n} étudiants sur {total} n'ont pas travaillé ces 7 derniers jours. Lodestar "
        "leur propose des séances courtes et faciles à leur retour.",
    },
    "tn": {
        "revisit": "عاودوا الnotes {section} ({name}) : {n} طلبة من {total} تحت {below}%",
        "mixup": "، و« {text} » تتعاود في أجوبة {n} طلبة",
        "quiet": "{n} طلبة من {total} ما قراوش في الـ7 أيام اللي فاتو. Lodestar يعطيهم "
        "séances قصيرة وساهلة كي يرجعو.",
    },
}


def _state(belief: Belief | None, norms: Norms, dim: str) -> ConceptState:
    if belief is None or belief.n == 0:
        return "not_checked"
    pct = norms.percentile(dim, belief)
    if pct.value < learning.STRUGGLING_PERCENT and pct.high < learning.STRUGGLING_HIGH:
        return "struggling"  # the same rule as the planner's (backend/agent/learning.py)
    return "solid" if pct.value >= SOLID_PERCENT else "shaky"


@router.get("/course", response_model=CourseMapView)
async def course_map(conn: Conn, user_id: CurrentUser, registry: RegistryDep) -> CourseMapView:
    if not registry.courses:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No course loaded")
    course = registry.course
    norms = Norms()
    now = datetime.now(UTC)
    twin = await read_twin(conn, user_id, now=now, norms=norms)
    beliefs = {v.dim: Belief(v.mu, v.sigma, v.n, v.last_practised) for v in twin.dims}
    patterns = await read_patterns(conn, user_id, registry, norms, formats_by_dim(registry), now)
    plateaus = {p.dim for p in patterns.plateaus}
    mistakes = await learning.misconception_counts(conn, registry, user_id)
    gap = learning.find_gap(course, beliefs, {}, norms)
    blocking: dict[str, list[str]] = {}
    for target in learning.struggling(course, beliefs, norms):
        found = learning.find_gap(course, beliefs, {}, norms, concept=target)
        if found is not None:
            blocking.setdefault(found.prereq, []).append(target)
    exam = (
        await conn.execute(
            select(func.min(t.goals.c.due)).where(
                t.goals.c.user_id == user_id,
                t.goals.c.status == "active",
                t.goals.c.due >= now.date(),
            )
        )
    ).scalar_one_or_none()

    concepts = []
    for c in course.concepts:
        b = beliefs.get(c.id)
        pct = norms.percentile(c.id, b) if b is not None and b.n > 0 else None
        mine = [m for m in mistakes if m.concept == c.id]
        concepts.append(
            ConceptStatus(
                id=c.id,
                name=c.name,
                plain=c.plain,
                section=c.section,
                chapter=course.chapter(c),
                requires=c.requires,
                key_ideas=c.key_ideas,
                n=b.n if b else 0,
                percent=round(pct.value, 1) if pct else None,
                low=round(pct.low, 1) if pct else None,
                high=round(pct.high, 1) if pct else None,
                state=_state(b, norms, c.id),
                plateau=c.id in plateaus,
                review_due=bool(b and pct and learning.review_due(b, pct, now)),
                blocking=blocking.get(c.id, []),
                mistake=mine[0].text if mine else None,
                mistakes=sum(m.count for m in mine),
            )
        )
    return CourseMapView(
        course=course.id,
        name=course.name,
        audience=course.audience,
        source_title=course.source.title,
        source_url=str(course.source.url),
        concepts=concepts,
        sections=[SectionView(id=s.id, title=s.title, text=s.text) for s in course.sections],
        gap=GapView(concept=gap.concept, prereq=gap.prereq, chain=gap.chain) if gap else None,
        exam=exam,
    )


@router.get("/class", response_model=ClassView)
async def class_view(engine: Engine, user_id: CurrentUser, registry: RegistryDep) -> ClassView:
    """Everyone studying the course on this server, as counts and medians only. In a school
    deployment this sits behind a teacher role; the demo lets any signed-in user open it."""
    if not registry.courses:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No course loaded")
    course = registry.course
    norms = Norms()
    now = datetime.now(UTC)
    concept_ids = {c.id for c in course.concepts}
    concept_col = t.trials.c.stimulus["concept"].astext
    tag_col = t.trials.c.response["misconception"].astext
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                select(t.dimension_state).where(t.dimension_state.c.dim.in_(concept_ids))
            )
        ).all()
        last_seen = dict(
            (
                await conn.execute(
                    select(t.trials.c.user_id, func.max(t.trials.c.ts)).group_by(t.trials.c.user_id)
                )
            ).all()
        )
        by_mistake = (
            await conn.execute(
                select(
                    concept_col,
                    tag_col,
                    func.count(distinct(t.trials.c.user_id)),
                    func.count(),
                    func.count().filter(t.trials.c.confidence >= 0.75),
                )
                .where(
                    t.trials.c.game_id.like("quiz_%"),
                    t.trials.c.correct.is_(False),
                    tag_col.is_not(None),
                )
                # The same expression objects, so Postgres sees one grouping expression each.
                .group_by(concept_col, tag_col)
            )
        ).all()

    percents: dict[str, list[float]] = {c: [] for c in concept_ids}
    for r in rows:
        if r.n > 0:
            belief = drift(Belief(r.mu, r.sigma, r.n, r.last_practised), now)
            percents[r.dim].append(norms.percentile(r.dim, belief).value)
    students = len(last_seen)
    week = now - timedelta(days=7)
    active = sum(1 for ts in last_seen.values() if ts >= week)

    concepts = [
        ClassConcept(
            id=c.id,
            name=c.name,
            chapter=course.chapter(c),
            section=c.section,
            students=len(percents[c.id]),
            median_percent=round(median(percents[c.id]), 1) if percents[c.id] else None,
            struggling=sum(p < learning.STRUGGLING_PERCENT for p in percents[c.id]),
            solid=sum(p >= SOLID_PERCENT for p in percents[c.id]),
        )
        for c in course.concepts
    ]
    mistakes = []
    for concept_id, tag, n_students, n, sure in by_mistake:
        if concept_id not in concept_ids:
            continue
        concept = course.concept(concept_id)
        m = concept.misconception(tag)
        if m is not None:
            mistakes.append(
                ClassMistake(
                    concept=concept.id,
                    concept_name=concept.name,
                    id=m.id,
                    text=m.text,
                    fix=m.fix,
                    students=int(n_students),
                    count=int(n),
                    confident=int(sure),
                )
            )
    mistakes.sort(key=lambda m: (-m.students, -m.count))

    suggestions = []
    hardest = sorted(
        (c for c in concepts if c.students >= 3),
        key=lambda c: (-c.struggling / c.students, c.median_percent or 0),
    )
    say = _SUGGEST[i18n.current()]
    for c in hardest[:2]:
        top = next((m for m in mistakes if m.concept == c.id), None)
        line = say["revisit"].format(
            section=c.section,
            name=c.name,
            n=c.struggling,
            total=c.students,
            below=round(learning.STRUGGLING_PERCENT),
        )
        if top is not None:
            line += say["mixup"].format(
                text=f"{top.text[:1].lower()}{top.text[1:]}", n=top.students
            )
        suggestions.append(line + ".")
    if students and active < students:
        suggestions.append(say["quiet"].format(n=students - active, total=students))
    return ClassView(
        course=course.name,
        students=students,
        active_week=active,
        drifting=students - active,
        concepts=concepts,
        mistakes=mistakes[:CLASS_MISTAKES],
        suggestions=suggestions,
    )
