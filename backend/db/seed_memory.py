"""Memory notes for the demo user (docs/plan/04): a few core.md lines and some remembered moments
and facts in Qdrant, so the Memory page has something to show. Runs where the app's memory lives,
inside the backend container: `make seed` calls it after `backend.db.seed`."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from backend.config import get_settings, qdrant_client
from backend.db import tables as t
from backend.db.engine import get_engine
from backend.db.seed import DEMO_NAME
from backend.memory.embeddings import Embedder
from backend.memory.notes import Notes
from backend.memory.store import MemoryStore

CORE = [
    "First-year student; Probability 1 exam on the first of December.",
    "Studies best in the afternoon, between lectures.",
    "Wants Bayes' theorem solid before the exam.",
    "Prefers short sessions on days with lab work.",
    "Calm, short explanations work best; likes a worked example.",
    "Works at a cafe on Saturdays, so weekends are short.",
    "Likes to see the range, not just the number.",
    "Says conditional probability 'makes sense in class and then disappears'.",
]
# (days ago, collection, kind, text)
MOMENTS = [
    (1, "episodic", "moment", "Did four quizzes in one go and slowed down on the last one."),
    (
        2,
        "episodic",
        "moment",
        "Got the fire alarm question wrong and asked why the answer was so low.",
    ),
    (4, "episodic", "milestone", "Finished the late-night revision experiment: too close to call."),
    (
        5,
        "episodic",
        "preference",
        "Asked for explanations with a table of counts instead of formulas.",
    ),
    (9, "episodic", "moment", "Had a cold; kept to one short quiz a day."),
    (12, "episodic", "milestone", "Morning won the counting experiment."),
    (14, "episodic", "moment", "Said the lecture on conditional probability went too fast."),
    (
        20,
        "episodic",
        "moment",
        "Short nights before a lab report; sessions were shorter that week.",
    ),
    (27, "episodic", "milestone", "Chapter 1 quizzes all above 70% for the first time."),
    (34, "episodic", "moment", "First session: wanted to know how the concept map works."),
    (3, "facts", "fact", "Conditional probability hasn't moved in about two weeks of quizzes."),
    (6, "facts", "fact", "Most wrong answers on chapter 2 swap P(A | B) and P(B | A)."),
    (12, "facts", "fact", "Counting problems go better in the morning, from their own experiment."),
    (18, "facts", "fact", "Tends to slow down after about a quarter of an hour of quizzes."),
]


async def seed_memory(user_id: UUID | None = None, memory: MemoryStore | None = None) -> None:
    settings = get_settings()
    if user_id is None:
        with get_engine().connect() as conn:
            user_id = conn.execute(
                select(t.users.c.user_id).where(t.users.c.display_name == DEMO_NAME)
            ).scalar_one()
    Notes(settings.memory_dir).write_core(user_id, CORE)
    if memory is None:
        memory = MemoryStore(qdrant_client(settings, timeout=10), Embedder())
        await memory.ensure_collections()
    now = datetime.now(UTC)
    for days, collection, kind, text in MOMENTS:
        await memory.write(
            user_id, text, collection=collection, kind=kind,  # type: ignore[arg-type]
            importance=0.7, created_at=now - timedelta(days=days), confidence=0.8,
        )  # fmt: skip
    print(f"Wrote {len(CORE)} core lines and {len(MOMENTS)} memories for {DEMO_NAME}")


if __name__ == "__main__":
    asyncio.run(seed_memory())
