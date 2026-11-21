"""Converse tools for studying a course (docs/plan/19): explain a concept from the student's own
course notes, and show the mistakes they keep making. Both are read-only, answer from a facts
packet (AGENTS.md rule 4) and add a card to the conversation.

Every explanation cites the notes it comes from. The coach may reword the notes, never add to
them: the verifier rejects any number that isn't in a fact.
"""

import re
from dataclasses import replace
from typing import Any

from pydantic import Field

from backend.agent import learning
from backend.agent.context import LodestarContext
from backend.agent.state import LodestarState
from backend.agent.telemetry import emit
from backend.contracts.common import Contract, DimensionId
from backend.contracts.facts import Fact, FactsPacket
from backend.contracts.session import ToolCall, ToolOutcome
from backend.db.twin_store import read_twin
from backend.registry.course import Concept, Course
from backend.scoring.kalman_elo import Belief


class TeachArgs(Contract):
    dim: DimensionId | None = None
    question: str = Field(default="", max_length=500)


class MistakesArgs(Contract):
    dim: DimensionId | None = None
    question: str = Field(default="", max_length=500)


def _sentences(text: str, n: int) -> str:
    parts = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    return " ".join(parts[:n])


def _first_lower(text: str) -> str:
    """Lowercase the first letter only, so "P(A | B)" stays as written."""
    return text[:1].lower() + text[1:]


def which_concept(course: Course) -> str:
    names = ", ".join(c.name.lower() for c in course.concepts[4:8])
    return f"Which part of {course.name}? For example {names}."


def _passage(course: Course, concept: Concept) -> str:
    """The lines of the notes about this concept: the section's opening lines."""
    return _sentences(course.section(concept.section).text, 3)


async def teach(
    ctx: LodestarContext, state: LodestarState, call: ToolCall
) -> tuple[ToolOutcome, dict[str, Any]]:
    """ "I don't get Bayes": the notes on it, where the student stands, their usual mistake on it,
    and a shaky prerequisite if there is one. Then a quiz is one tap away."""
    args = TeachArgs.model_validate(call.args)
    registry = ctx.services.registry
    if not registry.courses:
        return ToolOutcome(name="teach", reply="There's no course loaded yet."), {}
    course = registry.course
    if args.dim is None or registry.course_of(args.dim) is None:
        return ToolOutcome(name="teach", reply=which_concept(course)), {}
    concept = course.concept(args.dim)
    section = course.section(concept.section)
    norms = ctx.services.norms
    async with ctx.services.engine.connect() as conn:
        twin = await read_twin(conn, ctx.user_id, norms=norms)
        mistakes = [
            m
            for m in await learning.misconception_counts(conn, registry, ctx.user_id)
            if m.concept == concept.id
        ]
    beliefs = {v.dim: Belief(v.mu, v.sigma, v.n) for v in twin.dims if v.n > 0}
    gap = learning.find_gap(course, beliefs, {}, norms, concept=concept.id)
    view = next((v for v in twin.dims if v.dim == concept.id and v.n > 0), None)
    passage = _passage(course, concept)

    facts = [
        Fact(id="F1", text=f"Notes {section.id}, {section.title}: {passage}", dim=concept.id),
        Fact(id="F2", text=f"Key ideas: {'; '.join(concept.key_ideas)}.", dim=concept.id),
    ]
    if view is not None:
        facts.append(
            Fact(
                id=f"F{len(facts) + 1}",
                text=f"{concept.name} mastery {round(view.percent)}% "
                f"(80% range {round(view.percent_low)}-{round(view.percent_high)}%)",
                dim=concept.id,
            )
        )
    mistake = mistakes[0] if mistakes else None
    if mistake is not None:
        facts.append(
            Fact(
                id=f"F{len(facts) + 1}",
                text=f"Usual mix-up on {concept.name.lower()}: {_first_lower(mistake.text)}, "
                f"{mistake.count} times. Fix: {mistake.fix}",
                dim=concept.id,
            )
        )
    gap_view = None
    if gap is not None:
        prereq = course.concept(gap.prereq)
        state_text = gap.prereq_pct.label() if gap.prereq_pct else "not checked yet"
        facts.append(
            Fact(
                id=f"F{len(facts) + 1}",
                text=f"{concept.name} builds on {prereq.name.lower()}, which is {state_text}",
                dim=prereq.id,
            )
        )
        gap_view = {
            "dim": prereq.id,
            "name": prereq.name,
            "section": prereq.section,
            "now": round(gap.prereq_pct.value) if gap.prereq_pct else None,
            "low": round(gap.prereq_pct.low) if gap.prereq_pct else None,
            "high": round(gap.prereq_pct.high) if gap.prereq_pct else None,
        }

    emit(
        {
            "kind": "card",
            "card": "lesson",
            "dim": concept.id,
            "name": concept.name,
            "section_id": section.id,
            "section_title": section.title,
            "passage": section.text.strip(),
            "key_ideas": concept.key_ideas,
            "mastery": (
                {
                    "now": round(view.percent),
                    "low": round(view.percent_low),
                    "high": round(view.percent_high),
                }
                if view is not None
                else None
            ),
            "mistake": (
                {
                    "text": mistake.text,
                    "fix": mistake.fix,
                    "count": mistake.count,
                    "confident": mistake.confident,
                }
                if mistake is not None
                else None
            ),
            "gap": gap_view,
        }
    )
    text = f"From your notes ({section.id}, {section.title}): {passage} [F1]"
    if mistake is not None:
        ref = next(f.id for f in facts if f.text.startswith("Usual mix-up"))
        text += f" The mix-up I see most in your answers: {_first_lower(mistake.text)} [{ref}]. "
        text += mistake.fix
    if gap is not None:
        ref = facts[-1].id
        text += (
            f" It builds on {course.concept(gap.prereq).name.lower()}, which is still shaky "
            f"[{ref}], so that's worth a look first."
        )
    text += " Want five questions on it?"
    instruction = (
        f'The user asked: "{args.question}". Explain {concept.name.lower()} in plain words using '
        "only the course notes and key ideas in the facts, citing them, in at most 5 sentences. "
        "If a fact names their usual mix-up, say it and the fix. If a fact says it builds on a "
        "shaky concept, say so. End by offering five questions. Add no formula, number or example "
        "that isn't in the facts."
    )
    return ToolOutcome(
        name="teach", facts=FactsPacket(facts=facts), instruction=instruction, fallback=text
    ), {}


async def mistakes(
    ctx: LodestarContext, state: LodestarState, call: ToolCall
) -> tuple[ToolOutcome, dict[str, Any]]:
    """ "What do I keep getting wrong?": the misconceptions behind the student's wrong answers,
    most frequent first, with how often they were sure, and the fix for each."""
    args = MistakesArgs.model_validate(call.args)
    registry = ctx.services.registry
    async with ctx.services.engine.connect() as conn:
        found = await learning.misconception_counts(conn, registry, ctx.user_id)
    if args.dim is not None:
        found = [m for m in found if m.concept == args.dim]
    else:
        # The same mix-up on several concepts is one habit: count it once, on all of them.
        merged: dict[str, learning.MisconceptionCount] = {}
        for m in found:
            if m.id in merged:
                k = merged[m.id]
                merged[m.id] = replace(
                    k,
                    concept_name=f"{k.concept_name} and {m.concept_name.lower()}",
                    count=k.count + m.count,
                    confident=k.confident + m.confident,
                )
            else:
                merged[m.id] = m
        found = sorted(merged.values(), key=lambda m: -m.count)
    if not found:
        reply = (
            "I haven't seen a pattern in your wrong answers yet. A few quizzes and I'll be able "
            "to tell a slip from a real mix-up."
        )
        return ToolOutcome(name="mistakes", reply=reply), {}
    top = found[:3]
    facts = [
        Fact(
            id=f"F{i + 1}",
            text=f"On {m.concept_name.lower()}: {_first_lower(m.text)}, {m.count} times, "
            f"{m.confident} of them while sure. Fix: {m.fix}",
            dim=m.concept,
        )
        for i, m in enumerate(top)
    ]
    emit(
        {
            "kind": "card",
            "card": "mistakes",
            "rows": [
                {
                    "dim": m.concept,
                    "concept": m.concept_name,
                    "text": m.text,
                    "fix": m.fix,
                    "count": m.count,
                    "confident": m.confident,
                }
                for m in top
            ],
        }
    )
    first = top[0]
    text = (
        f"The mix-up I see most: {_first_lower(first.text)}, {first.count} times on "
        f"{first.concept_name.lower()}, {first.confident} of them when you were sure [F1]. "
        f"{first.fix}"
    )
    if len(top) > 1:
        text += f" Next: {_first_lower(top[1].text)} [F2]."
    instruction = (
        f'The user asked: "{args.question}". Name their most frequent mix-up and its fix from the '
        "facts, then the next one, in at most 4 sentences. Say that being sure and wrong is "
        "normal for a mix-up and that the fix is worth reading once."
    )
    return ToolOutcome(
        name="mistakes", facts=FactsPacket(facts=facts), instruction=instruction, fallback=text
    ), {}
