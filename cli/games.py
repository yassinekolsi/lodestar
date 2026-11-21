"""Text versions of the exercises the registry marks `terminal: true` (UW19, docs/plan/19).

Course exercises are played by two plugins, the quiz and explain it back. Each text version plays
the content the server sent and records the same trials, with the same rules, as its browser
plugin in `frontend/src/games/<plugin>/plugin.ts`: the same right-or-wrong rule, the same hint
ladder, the same "How sure?" question and the same explain-it-back rubric.
"""

import re
import statistics
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from cli.client import Io


class NoContent(Exception):
    """The round came without its content; the browser can still play it."""


class Stopped(Exception):
    """The user typed q."""


@dataclass
class Played:
    answers: list[dict[str, Any]] = field(default_factory=list)
    stopped: bool = False

    def add(
        self,
        stimulus: dict[str, Any],
        response: Any,
        correct: bool | None,
        rt_ms: float | None,
        hint_level: int = 0,
        confidence: float | None = None,
    ) -> None:
        self.answers.append(
            {
                "trial_index": len(self.answers),
                "practice": False,
                "stimulus": stimulus,
                "response": response,
                "correct": correct,
                "rt_ms": None if rt_ms is None else round(rt_ms, 1),
                "hint_level": hint_level,
                "confidence": confidence,
                "ts": datetime.now(UTC).isoformat(),
            }
        )

    def scored(self) -> list[dict[str, Any]]:
        return [a for a in self.answers if a["correct"] is not None]

    def accuracy(self) -> float:
        s = self.scored()
        return sum(a["correct"] for a in s) / len(s) if s else 0.0


def _read(io: Io, prompt: str) -> str:
    try:
        line = io.read(prompt)
    except EOFError as exc:
        raise Stopped from exc
    if line.strip().lower() in ("q", "quit", "stop"):
        raise Stopped
    return line


# The quiz -------------------------------------------------------------------------------------

SURE = {"1": 0.5, "2": 0.75, "3": 1.0}


def _pick(io: Io, q: dict[str, Any]) -> tuple[int, int]:
    """The chosen option and how many hints were opened first."""
    gone: set[int] = set()
    hints = 0
    while True:
        typed = _read(io, "Answer (1-4, h for a hint, q to stop): ").strip().lower()
        if typed == "h" and hints < len(q["hints"]):
            io.console.print(f"[dim]{q['hints'][hints]}[/dim]")
            if hints == 1:
                gone = set(q["remove"])
                left = [str(i + 1) for i in range(len(q["options"])) if i not in gone]
                io.console.print(f"[dim]Still in: {', '.join(left)}[/dim]")
            hints += 1
        elif typed.isdigit() and 0 < int(typed) <= len(q["options"]):
            if int(typed) - 1 not in gone:
                return int(typed) - 1, hints


async def quiz(io: Io, spec: dict[str, Any], played: Played) -> dict[str, float]:
    content = spec.get("content") or {}
    questions = content.get("questions") or []
    if not questions:
        raise NoContent
    section = content.get("section") or {}
    for n, q in enumerate(questions, start=1):
        io.console.print(f"\n[bold]Question {n} of {len(questions)}[/bold]  {q['stem']}")
        for i, o in enumerate(q["options"]):
            io.console.print(f"  {i + 1}. {o['text']}")
        started = time.monotonic()
        choice, hints = _pick(io, q)
        rt = (time.monotonic() - started) * 1000
        sure = None
        while sure is None:
            sure = SURE.get(_read(io, "How sure? 1 guessing, 2 fairly sure, 3 sure: ").strip())
        correct = choice == q["answer"]
        tag = q["options"][choice].get("misconception")
        if correct:
            io.console.print("[green]Right.[/green]")
        else:
            io.console.print("[red]Not quite.[/red]")
            fix = (q.get("fixes") or {}).get(tag) if tag else None
            if fix:
                lead = "A common mix-up, and you were sure" if sure >= 0.75 else "A common mix-up"
                io.console.print(f"{lead}: {fix['text']}. {fix['fix']}")
        io.console.print(q["explain"])
        io.console.print(f"[dim]Notes {section.get('id', '')}, {section.get('title', '')}[/dim]")
        played.add(
            {
                "question_id": q["id"],
                "concept": content.get("concept"),
                "level": q["level"],
                "options": [o["text"] for o in q["options"]],
            },
            {"choice": choice, "misconception": None if correct else tag, "hints": hints},
            correct,
            rt,
            hint_level=hints,
            confidence=sure,
        )
    scored = played.scored()
    out = {
        "accuracy": played.accuracy(),
        "confident_errors": float(
            sum(1 for a in scored if not a["correct"] and (a["confidence"] or 0) >= 0.75)
        ),
    }
    rts = [a["rt_ms"] for a in scored if a["rt_ms"] is not None]
    if rts:
        out["median_rt_ms"] = statistics.median(rts)
    return out


# Explain it back ------------------------------------------------------------------------------

WORD = re.compile(r"[a-z]+")
ENOUGH_WORDS = 25


def rubric(text: str, ideas: list[dict[str, Any]]) -> tuple[float, list[bool]]:
    """The browser's rule (frontend/src/games/explain/plugin.ts) and the server's
    (backend/agent/learning.py, rubric_score)."""
    found = {w[:5] for w in WORD.findall(text.lower())}
    hits = []
    for idea in ideas:
        words = list(idea["words"])
        need = max(1, (len(words) + 1) // 2)
        hits.append(sum(w in found for w in words) >= need)
    share = sum(hits) / len(hits) if hits else 0.0
    return share * min(1.0, len(re.findall(r"\w+", text)) / ENOUGH_WORDS), hits


async def explain(io: Io, spec: dict[str, Any], played: Played) -> dict[str, float]:
    content = spec.get("content") or {}
    ideas = content.get("key_ideas") or []
    if not ideas:
        raise NoContent
    io.console.print(f"\n[bold]Explain it back: {content.get('concept_name', '')}[/bold]")
    io.console.print(content.get("prompt", ""))
    started = time.monotonic()
    text = _read(io, "Your explanation (one line): ")
    score, hits = rubric(text, ideas)
    io.console.print(f"You covered {sum(hits)} of the {len(hits)} key ideas:")
    for idea, hit in zip(ideas, hits, strict=True):
        io.console.print(f"  {'✓' if hit else '○'} {idea['text']}")
    played.add(
        {"concept": content.get("concept"), "ideas": len(ideas)},
        {
            "score": score,
            "covered": [i["text"] for i, h in zip(ideas, hits, strict=True) if h],
            "text": text[:2000],
        },
        None,
        (time.monotonic() - started) * 1000,
    )
    return {"rubric_score": score}


Game = Callable[[Io, dict[str, Any], Played], Awaitable[dict[str, float]]]
GAMES: dict[str, Game] = {"quiz": quiz, "explain": explain}


async def play(io: Io, spec: dict[str, Any]) -> dict[str, Any]:
    """Play one round and return the arguments for the `finish_round` tool. Raises NoContent if
    the round can't be played as text."""
    plugin = spec.get("plugin") or spec["game_id"]
    if plugin not in GAMES:
        raise NoContent
    started = datetime.now(UTC)
    played = Played()
    metrics: dict[str, float] = {}
    try:
        metrics = await GAMES[plugin](io, spec, played)
    except Stopped:
        played.stopped = True
    return {
        "round_id": spec["round_id"],
        "answers": played.answers,
        "metrics": metrics,
        "status": "stopped" if played.stopped else "completed",
        "stop_reason": "user" if played.stopped else None,
        "started_at": started.isoformat(),
        "ended_at": datetime.now(UTC).isoformat(),
    }
