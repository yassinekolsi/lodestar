"""`make seed`: Alex, a first-year student five weeks into Probability 1, and 24 classmates for the
teacher view (docs/plan/19). Alex's memory notes are written by `backend.db.seed_memory`, which
runs inside the backend container. The "Demo" button in the app does the same through
`POST /demo` (backend/api/demo.py).

Every answer is a real question from the course, answered by a simulated student with a known
true level per concept, and every estimate comes from the real scorer (backend/scoring/rounds.py)
fed those answers in order. So the profile, the history and the patterns the demo shows are what
Lodestar would compute from the stored answers, not numbers written by hand.

Alex's story: chapter 1 went well; conditional probability has stayed near 40% for three weeks of
quizzes (a plateau), Bayes' theorem is low because it builds on it (a prerequisite gap), the same
two misconceptions keep coming back, and the exam is in ten days.
"""

import argparse
import math
import random
import secrets
import zlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from psycopg.types.range import Range
from sqlalchemy import Connection, func, insert, select

from backend.agent.experiments import compare, design
from backend.contracts.trial import TrialEvent
from backend.db import tables as t
from backend.db.engine import get_engine
from backend.db.twin_store import hash_token
from backend.registry.course import Course
from backend.registry.loader import load_registry
from backend.registry.models import Game, Registry
from backend.scoring.kalman_elo import Belief, drift
from backend.scoring.levels import TARGET_P, b_for_level, choose_mode, next_level
from backend.scoring.loadings import loading_matrix
from backend.scoring.rounds import score_round

DEMO_NAME = "Alex"
CLASSMATE_PREFIX = "Classmate "
CLASSMATES = 24
DAYS = 35
EXAM_IN_DAYS = 10
SEED = 7

# When each concept is taught (day of the semester), in course order.
TAUGHT = {
    "sample_space": 0, "counting": 3, "equally_likely": 6, "addition_rule": 9,
    "conditional": 12, "independence": 16, "total_probability": 19, "bayes": 22,
    "random_variables": 26, "expectation": 29, "variance": 33, "binomial": 99,
}  # fmt: skip

# Alex's true level per concept (logit scale) at the start and at the end of the five weeks.
ALEX_TRUE = {
    "sample_space": (1.2, 1.9), "counting": (0.4, 1.2), "equally_likely": (0.8, 1.5),
    "addition_rule": (0.3, 1.0), "conditional": (-0.45, -0.45), "independence": (0.0, 0.5),
    "total_probability": (-0.1, 0.3), "bayes": (-1.5, -1.5), "random_variables": (0.6, 0.9),
    "expectation": (0.3, 0.6), "variance": (0.0, 0.0), "binomial": (0.0, 0.0),
}  # fmt: skip
# The wrong answers Alex tends to pick when one of them is on offer.
ALEX_HABITS = {"inverse_conditional": 0.85, "base_rate_neglect": 0.7, "conditional_as_joint": 0.6,
               "double_count_union": 0.4, "order_confusion": 0.4}  # fmt: skip
# Alex keeps coming back to conditional probability once it's taught, without it moving.
STUCK = "conditional"

LIFE = [("short nights", -20, 3), ("cold", -9, 3), ("exam week", EXAM_IN_DAYS, 6)]
HARD_TIMES = {"short nights", "cold"}

# Classmates: the class finds the same things hard (chapter 2), each with their own habits.
CLASS_MISCONCEPTIONS = ["inverse_conditional", "base_rate_neglect", "double_count_union",
                        "gamblers_fallacy", "order_confusion", "exclusive_independent",
                        "average_unweighted", "variance_linear"]  # fmt: skip
CLASS_MEAN = {
    "sample_space": 1.4, "counting": 0.6, "equally_likely": 0.9, "addition_rule": 0.5,
    "conditional": -0.2, "independence": 0.1, "total_probability": 0.0, "bayes": -0.9,
    "random_variables": 0.7, "expectation": 0.4, "variance": -0.1, "binomial": 0.0,
}  # fmt: skip


def _ts(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def tracked_dims(registry: Registry) -> list[str]:
    """Every concept of the course."""
    return [d.id for d in registry.dimensions if not d.style]


@dataclass
class Student:
    """A simulated student: true level per concept over time, and favourite wrong answers."""

    true: dict[str, tuple[float, float]]
    habits: dict[str, float]
    rng: random.Random
    beliefs: dict[str, Belief] = field(default_factory=dict)

    def level_on(self, concept: str, progress: float) -> float:
        start, end = self.true[concept]
        return start + (end - start) * progress


@dataclass
class Played:
    round_id: UUID
    game: Game
    started: datetime
    trials: list[TrialEvent]
    score: float | None


def _answer(
    student: Student, course: Course, game: Game, theta: float, level: float,
    seen: set[str], session_id: UUID, round_id: UUID, started: datetime, hard: bool,
) -> list[TrialEvent]:  # fmt: skip
    """One round of a quiz or an explanation, answered by the student."""
    rng = student.rng
    concept = course.concept(game.primary_dims[0])
    trials: list[TrialEvent] = []
    if game.plugin_id == "explain":
        score = max(0.2, min(1.0, 1 / (1 + math.exp(-theta)) + rng.uniform(-0.15, 0.1)))
        trials.append(
            TrialEvent(
                trial_id=uuid4(), round_id=round_id, session_id=session_id, game_id=game.id,
                level=level, trial_index=0, stimulus={"concept": concept.id},
                response={"score": round(score, 2), "text": "(seeded explanation)"},
                rt_ms=round(rng.uniform(60_000, 150_000)), ts=started + timedelta(minutes=2),
            )
        )  # fmt: skip
        return trials
    ranked = sorted(concept.questions, key=lambda q: (q.id in seen, abs(q.level - level)))
    for i, q in enumerate(sorted(ranked[:5], key=lambda q: q.level)):
        seen.add(q.id)
        p = 1 / (1 + math.exp(-(theta - b_for_level(q.level) - (0.3 if hard else 0.0))))
        hints = 1 if rng.random() < 0.12 and q.level > 0.5 else 0
        correct = rng.random() < p + 0.08 * hints
        tag = None
        if not correct:
            wrong = [o for o in q.options if not o.correct]
            habit = [o for o in wrong if o.misconception and rng.random() < student.habits.get(
                o.misconception, 0.15)]  # fmt: skip
            tag = (habit[0] if habit else rng.choice(wrong)).misconception
        sure = rng.choice([0.6, 0.7, 0.8, 0.9, 1.0]) if i % 2 == 1 else None
        trials.append(
            TrialEvent(
                trial_id=uuid4(), round_id=round_id, session_id=session_id, game_id=game.id,
                level=q.level, trial_index=i,
                stimulus={"question_id": q.id, "concept": concept.id},
                response={"misconception": tag} if tag else {"choice": "right" if correct else "x"},
                correct=correct, rt_ms=round(rng.lognormvariate(9.85, 0.35), 1),
                hint_level=hints, confidence=sure, ts=started + timedelta(seconds=25 * (i + 1)),
            )
        )  # fmt: skip
    return trials


def _play_round(
    student: Student, registry: Registry, game: Game, session_id: UUID, started: datetime,
    progress: float, seen: set[str], hard: bool, loadings: Mapping[str, Mapping[str, float]],
) -> Played:  # fmt: skip
    concept = game.primary_dims[0]
    loads = loadings[game.id]
    before = {d: drift(student.beliefs.get(d, Belief()), started) for d in loads}
    mode = choose_mode(before[concept], "balanced")
    level = next_level(before[concept], TARGET_P[mode])
    round_id = uuid4()
    trials = _answer(
        student, registry.course, game, student.level_on(concept, progress), level, seen,
        session_id, round_id, started, hard,
    )  # fmt: skip
    outcome = score_round(
        game, trials, before, loads, context_weight=0.5 if hard else 1.0, chance=game.chance
    )
    if outcome.observations:
        student.beliefs.update(outcome.beliefs)
    return Played(round_id, game, started, trials, outcome.mean_score)


def _insert_round(conn: Connection, user_id: UUID, session_id: UUID, played: Played) -> None:
    conn.execute(
        insert(t.rounds).values(
            round_id=played.round_id, user_id=user_id, session_id=session_id,
            game_id=played.game.id, level=played.trials[0].level, status="completed",
            score=played.score, started_at=played.started,
            ended_at=played.started + timedelta(minutes=3),
            scored_at=played.started + timedelta(minutes=3),
        )
    )  # fmt: skip
    rows = [{**tr.model_dump(), "user_id": user_id, "practice": False} for tr in played.trials]
    conn.execute(insert(t.trials), rows)
    conn.execute(
        insert(t.events),
        [
            {
                "user_id": user_id, "session_id": session_id, "ts": tr.ts,
                "type": "trial.recorded", "payload": tr.model_dump(mode="json"),
            }
            for tr in played.trials
        ],
    )  # fmt: skip


def _simulate(
    conn: Connection, registry: Registry, user_id: UUID, student: Student, today: date,
    study_days: float, sessions_rounds: tuple[int, int], stuck: str | None, history: bool,
    stopped_days_ago: int = 0,
) -> list[tuple[UUID, datetime]]:  # fmt: skip
    """Five weeks of study sessions, written as sessions, rounds, trials and events."""
    rng = student.rng
    start = today - timedelta(days=DAYS)
    loadings = loading_matrix(registry)
    hard_days = {
        today + timedelta(days=b + i)
        for label, b, n in LIFE
        if label in HARD_TIMES
        for i in range(n)
    }
    seen: dict[str, set[str]] = {}
    sessions: list[tuple[UUID, datetime]] = []
    for offset in range(DAYS):
        day = start + timedelta(days=offset)
        if stopped_days_ago and offset >= DAYS - stopped_days_ago:
            break  # drifted away
        streak = not stopped_days_ago and offset >= DAYS - 4  # a streak in the last few days
        if not streak and rng.random() > study_days:
            continue
        taught = [c for c, d in TAUGHT.items() if d <= offset]
        if not taught:
            continue
        hour = rng.choice([9, 14, 17, 20, 21, 22])
        session_id = uuid4()
        sessions.append((session_id, _ts(day, hour)))
        conn.execute(
            insert(t.sessions).values(
                session_id=session_id, user_id=user_id, trigger="ui", status="ended",
                started_at=_ts(day, hour), ended_at=_ts(day, hour, 20),
            )
        )  # fmt: skip
        conn.execute(
            insert(t.events).values(
                user_id=user_id, session_id=session_id, ts=_ts(day, hour),
                type="session.started", payload={"trigger": "ui", "persona": "willow"},
            )
        )  # fmt: skip
        # Mostly the newest concepts, some review, and the stuck one nearly every time.
        n = rng.randint(*sessions_rounds)
        newest = taught[-3:]
        picks = [
            rng.choice(newest) if rng.random() < 0.65 else rng.choice(taught) for _ in range(n)
        ]
        if stuck in taught and stuck not in picks and rng.random() < 0.85:
            picks[0] = stuck
        for r, concept in enumerate(dict.fromkeys(picks)):
            explain = rng.random() < 0.12 and concept != stuck
            game = registry.game(f"{'explain' if explain else 'quiz'}_{concept}")
            played = _play_round(
                student, registry, game, session_id, _ts(day, hour, 1 + 4 * r), offset / DAYS,
                seen.setdefault(game.id, set()), day in hard_days, loadings,
            )  # fmt: skip
            _insert_round(conn, user_id, session_id, played)
        if history:
            for dim, b in student.beliefs.items():
                conn.execute(
                    insert(t.history).values(
                        user_id=user_id, day=day, dim=dim, mu=b.mu, sigma=b.sigma, n=b.n
                    )
                )
        conn.execute(
            insert(t.events).values(
                user_id=user_id, session_id=session_id, ts=_ts(day, hour, 20),
                type="session.ended", payload={"reason": "budget", "rounds": n, "minutes": 4 * n},
            )
        )  # fmt: skip
    for dim, b in student.beliefs.items():
        conn.execute(
            insert(t.dimension_state).values(
                user_id=user_id, dim=dim, mu=b.mu, sigma=b.sigma, n=b.n,
                last_practised=b.last_practised,
            )
        )  # fmt: skip
    return sessions


def _consent(conn: Connection, registry: Registry, user_id: UUID, at: datetime) -> None:
    for switch, granted in [
        ("core", True), ("cloud_ai", False), ("microphone", True), ("camera", False),
        ("voice_tone", False), ("deliberate_mistakes", True), ("research_export", False),
    ]:  # fmt: skip
        conn.execute(
            insert(t.consent).values(
                user_id=user_id, switch=switch, granted=granted,
                notice_version=registry.consent.version, changed_at=at,
            )
        )  # fmt: skip


def seed_demo_user(conn: Connection, today: date | None = None) -> UUID:
    rng = random.Random(SEED)
    today = today or datetime.now(UTC).date()
    registry = load_registry()
    start = today - timedelta(days=DAYS)

    user_id: UUID = conn.execute(
        insert(t.users)
        .values(display_name=DEMO_NAME, persona="willow", age_confirmed=True)
        .returning(t.users.c.user_id)
    ).scalar_one()
    _consent(conn, registry, user_id, _ts(start, 20))
    exam = today + timedelta(days=EXAM_IN_DAYS)
    for dim, kind, target in [("bayes", "score", 70), ("conditional", "score", 75)]:
        conn.execute(
            insert(t.goals).values(user_id=user_id, dim=dim, kind=kind, target=target, due=exam)
        )
    for label, begin, days in LIFE:
        day = today + timedelta(days=begin)
        conn.execute(
            insert(t.life_context).values(
                user_id=user_id, label=label,
                period=Range(_ts(day, 0), _ts(day + timedelta(days=days), 0)), weight=0.5,
            )
        )  # fmt: skip

    alex = Student(true=dict(ALEX_TRUE), habits=dict(ALEX_HABITS), rng=rng)
    sessions = _simulate(conn, registry, user_id, alex, today, 0.75, (3, 4), STUCK, history=True)

    for component, rate in {"V": 0.55, "A": 0.6, "I": 0.5, "C": 0.45, "R": 0.8}.items():
        for _ in range(40):
            conn.execute(
                insert(t.acs_observations).values(
                    user_id=user_id, component=component, success=rng.random() < rate,
                    source="seed",
                )
            )  # fmt: skip
    _seed_experiments(conn, user_id, rng, today)
    _seed_decisions(conn, user_id, rng, sessions[-20:], alex.beliefs, registry)
    seed_classmates(conn, registry, today)
    return user_id


def seed_classmates(conn: Connection, registry: Registry, today: date) -> None:
    """24 classmates on the same course, for the teacher view. Each has their own level per
    concept around the class's and two habitual misconceptions."""
    rng = random.Random(SEED + 1)
    conn.execute(t.users.delete().where(t.users.c.display_name.like(f"{CLASSMATE_PREFIX}%")))
    for i in range(CLASSMATES):
        user_id = conn.execute(
            insert(t.users)
            .values(display_name=f"{CLASSMATE_PREFIX}{i + 1:02d}", age_confirmed=True)
            .returning(t.users.c.user_id)
        ).scalar_one()
        _consent(conn, registry, user_id, _ts(today - timedelta(days=DAYS), 9))
        skill = rng.gauss(0, 0.6)
        true = {}
        for c, mean in CLASS_MEAN.items():
            level = mean + skill + rng.gauss(0, 0.5)
            true[c] = (level - 0.3, level + rng.uniform(0.0, 0.7))
        habits = {m: rng.uniform(0.5, 0.85) for m in rng.sample(CLASS_MISCONCEPTIONS, 2)}
        habits["inverse_conditional"] = max(habits.get("inverse_conditional", 0), 0.5)
        student = Student(true=true, habits=habits, rng=random.Random(rng.random()))
        # A few have drifted away lately: they stopped studying a week or two ago.
        study = rng.choice([0.35, 0.45, 0.55, 0.65])
        stopped = rng.choice([9, 12, 15]) if i % 6 == 0 else 0
        _simulate(
            conn, registry, user_id, student, today, study, (2, 3), None, history=False,
            stopped_days_ago=stopped,
        )  # fmt: skip


def _seed_experiments(conn: Connection, user_id: UUID, rng: random.Random, today: date) -> None:
    """Two finished time-of-day experiments on study sessions: one where the morning won, one too
    close to call. None is left running, so the demo can start a new one."""
    for hypothesis, games, dim, (m_lo, m_hi), (e_lo, e_hi), ago in [
        ("I solve counting problems better in the morning",
         ["quiz_counting", "quiz_equally_likely"], "counting", (0.72, 0.85), (0.58, 0.7), 12),
        ("Late-night revision works as well as afternoon revision",
         ["quiz_addition_rule", "quiz_sample_space"], "addition_rule", (0.6, 0.72),
         (0.6, 0.73), 4),
    ]:  # fmt: skip
        morning = [round(rng.uniform(m_lo, m_hi), 3) for _ in range(3)]
        evening = [round(rng.uniform(e_lo, e_hi), 3) for _ in range(3)]
        c = compare(morning, evening)
        sessions = [
            {"session_id": str(uuid4()), "condition": cond, "score": score}
            for cond, scores in (("morning", morning), ("evening", evening))
            for score in scores
        ]
        done = _ts(today - timedelta(days=ago), 21)
        conn.execute(
            insert(t.experiments).values(
                user_id=user_id, hypothesis=hypothesis, design=design(games, dim),
                status="completed" if c.verdict != "inconclusive" else "inconclusive",
                result={
                    "sessions": sessions, "verdict": c.verdict,
                    "p_evening_better": round(c.p_evening_better, 3),
                    "difference": round(c.difference, 4),
                    "interval": [round(c.low, 4), round(c.high, 4)],
                    "wins": c.wins, "pairs": c.pairs,
                },
                created_at=done - timedelta(days=10), updated_at=done,
            )
        )  # fmt: skip


def _seed_decisions(
    conn: Connection, user_id: UUID, rng: random.Random, sessions: list[tuple[UUID, datetime]],
    beliefs: dict[str, Belief], registry: Registry,
) -> None:  # fmt: skip
    """The agent's "which concept next" choice for recent sessions, with each score's parts."""
    names = {d.id: d.name.lower() for d in registry.dimensions}
    known = sorted(d for d, b in beliefs.items() if b.n)
    for session_id, at in sessions:
        candidates = []
        for dim in rng.sample(known, min(3, len(known))):
            parts = {
                "uncertainty": round(beliefs[dim].sigma / 1.5, 3),
                "staleness": round(rng.uniform(0, 1), 3),
                "goal_weight": 1.0 if dim in ("bayes", "conditional") else 0.0,
                "bandit_gain": round(rng.uniform(0, 0.4), 3),
                "repetition": float(rng.random() < 0.2),
            }
            score = parts["uncertainty"] + 0.6 * parts["staleness"] + 0.5 * parts["goal_weight"]
            candidates.append({"option": dim, "score": round(score, 4), "breakdown": parts})
        candidates.sort(key=lambda c: -float(c["score"]))  # type: ignore[arg-type]
        chosen = str(candidates[0]["option"])
        conn.execute(
            insert(t.decisions).values(
                decision_id=uuid4(), session_id=session_id, user_id=user_id, node="plan_next",
                question="Which concept and exercise next?", candidates=candidates,
                chosen=chosen,
                reason=f"I'm least sure about {names[chosen]}, so a quiz there tells me most.",
                ts=at,
            )
        )  # fmt: skip


def issue_token(conn: Connection, user_id: UUID) -> str:
    """A bearer token for the demo user, so the browser can sign in as them."""
    token = secrets.token_urlsafe(32)
    conn.execute(insert(t.user_tokens).values(token_hash=hash_token(token), user_id=user_id))
    return token


def demo_sign_in(conn: Connection) -> tuple[UUID, str, bool]:
    """The demo user and a fresh sign-in token for them, seeding them first if they're missing.
    Returns whether they were just created. Safe when two tabs ask at once."""
    conn.execute(select(func.pg_advisory_xact_lock(zlib.crc32(b"lodestar.demo"))))
    existing = conn.execute(
        select(t.users.c.user_id).where(t.users.c.display_name == DEMO_NAME)
    ).scalar_one_or_none()
    user_id = existing or seed_demo_user(conn)
    return user_id, issue_token(conn, user_id), existing is None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="delete earlier demo users first")
    parser.add_argument(
        "--token", action="store_true", help="print a sign-in token and link for the demo user"
    )
    args = parser.parse_args()
    with get_engine().begin() as conn:
        existing = conn.execute(
            select(t.users.c.user_id).where(t.users.c.display_name == DEMO_NAME)
        ).scalar_one_or_none()
        if args.reset:
            conn.execute(t.users.delete().where(t.users.c.display_name == DEMO_NAME))
            existing = None
        if existing is None:
            user_id = seed_demo_user(conn)
            print(f"Seeded demo user {DEMO_NAME} and {CLASSMATES} classmates: {user_id}")
        else:
            user_id = existing
            print(f"Demo user {DEMO_NAME} already exists ({user_id}); --reset recreates it.")
        if args.token:
            token = issue_token(conn, user_id)
            print(f"TOKEN={token}")
            print(f"Sign in as {DEMO_NAME}: http://localhost:5173/?signin={token}")
            print(f"Or in a terminal: bin/lodestar login --code {token}")


if __name__ == "__main__":
    main()
