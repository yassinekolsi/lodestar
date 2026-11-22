from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import Connection, Table, func, select

from backend.agent import learning
from backend.db import tables as t
from backend.db.seed import (
    CLASSMATE_PREFIX,
    CLASSMATES,
    DEMO_NAME,
    demo_sign_in,
    seed_demo_user,
    tracked_dims,
)
from backend.db.twin_store import hash_token
from backend.registry.loader import load_registry
from backend.scoring.kalman_elo import Belief
from backend.scoring.norms import Norms
from backend.scoring.patterns import HistoryPoint, find_plateau


def _count(conn: Connection, table: Table, user_id: object) -> int:
    query = select(func.count()).select_from(table).where(table.c.user_id == user_id)
    return int(conn.execute(query).scalar_one())


def test_seed_creates_a_consistent_demo_student_and_a_class(conn: Connection) -> None:
    user_id = seed_demo_user(conn)
    registry = load_registry()
    rounds = _count(conn, t.rounds, user_id)
    trials = _count(conn, t.trials, user_id)
    assert rounds > 0 and trials >= rounds  # a quiz has 5 answers, an explanation 1
    assert _count(conn, t.events, user_id) == trials + 2 * _count(conn, t.sessions, user_id)
    measured = _count(conn, t.dimension_state, user_id)
    assert 0 < measured <= len(tracked_dims(registry))
    assert _count(conn, t.history, user_id) > 0
    assert _count(conn, t.consent, user_id) == 5
    assert _count(conn, t.goals, user_id) == 2
    assert _count(conn, t.experiments, user_id) == 2
    assert _count(conn, t.decisions, user_id) > 0
    classmates = conn.execute(
        select(func.count())
        .select_from(t.users)
        .where(t.users.c.display_name.like(f"{CLASSMATE_PREFIX}%"))
    ).scalar_one()
    assert classmates == CLASSMATES
    # Every answer is a real question of the course.
    ids = conn.execute(
        select(t.trials.c.stimulus["question_id"].astext).where(
            t.trials.c.user_id == user_id, t.trials.c.game_id.like("quiz_%")
        )
    ).scalars()
    assert all(registry.course.find_question(q) is not None for q in ids)


def test_the_demo_shows_a_plateau_a_gap_and_a_recurring_mix_up(conn: Connection) -> None:
    """The story the demo tells comes out of the scorer, not from numbers written by hand."""
    user_id = seed_demo_user(conn)
    registry = load_registry()
    rows = conn.execute(select(t.dimension_state).where(t.dimension_state.c.user_id == user_id))
    beliefs = {r.dim: Belief(r.mu, r.sigma, r.n, r.last_practised) for r in rows}
    gap = learning.find_gap(registry.course, beliefs, {}, Norms())
    assert gap is not None and (gap.concept, gap.prereq) == ("bayes", "conditional")

    history = conn.execute(
        select(t.history).where(t.history.c.user_id == user_id, t.history.c.dim == "conditional")
    )
    points = [HistoryPoint(h.day, h.mu, h.n) for h in history]
    assert find_plateau(points, datetime.now(UTC).date()) is not None

    tags = Counter(
        conn.execute(
            select(t.trials.c.response["misconception"].astext).where(
                t.trials.c.user_id == user_id, t.trials.c.correct.is_(False)
            )
        ).scalars()
    )
    tags.pop(None, None)
    assert tags.most_common(1)[0][0] == "inverse_conditional"


def test_demo_sign_in_seeds_once_and_hands_out_fresh_tokens(conn: Connection) -> None:
    conn.execute(t.users.delete().where(t.users.c.display_name == DEMO_NAME))
    first, token_a, created_a = demo_sign_in(conn)
    again, token_b, created_b = demo_sign_in(conn)
    assert (created_a, created_b) == (True, False)
    assert first == again and token_a != token_b
    owners = conn.execute(
        select(t.user_tokens.c.user_id).where(
            t.user_tokens.c.token_hash.in_([hash_token(token_a), hash_token(token_b)])
        )
    ).scalars()
    assert set(owners) == {first}
