"""Converse tools for studying a course (docs/plan/19): explain a concept from the student's own
course notes, and show the mistakes they keep making. Both are read-only, answer from a facts
packet (AGENTS.md rule 4) and add a card to the conversation.

Every explanation cites the notes it comes from. The coach may reword the notes, never add to
them: the verifier rejects any number that isn't in a fact.
"""

import re
from dataclasses import replace
from typing import Any
from uuid import UUID

from pydantic import Field

from backend import i18n
from backend.agent import learning
from backend.agent.context import LodestarContext
from backend.agent.state import LodestarState
from backend.agent.telemetry import emit
from backend.contracts.common import Contract, DimensionId
from backend.contracts.facts import Fact, FactsPacket
from backend.contracts.session import ToolCall, ToolOutcome
from backend.db.twin_store import read_twin
from backend.documents import library
from backend.documents.math_text import safe_cut
from backend.memory.store import PassageHit
from backend.registry.course import Concept, Course
from backend.scoring.kalman_elo import Belief

DOC_PASSAGES = 3


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
    return i18n.text("which_concept", course=course.name, names=names)


# The replies used when no model answers (a template built only from facts), in each language.
# Facts stay in English for the model, which is told to answer in the student's language.
_SAY: dict[str, dict[i18n.Locale, str]] = {
    "no_course": {
        "en": "Upload your course notes and I'll answer from them.",
        "fr": "Importe tes notes de cours et je répondrai à partir d'elles.",
        "tn": "حطّ الnotes متاع الcours متاعك ونجاوبك منهم.",
    },
    "also_upload": {
        "en": " You can also upload your own notes or slides in Documents, and I'll answer "
        "from them.",
        "fr": " Tu peux aussi importer tes notes ou tes slides dans Documents, et je répondrai à "
        "partir d'elles.",
        "tn": " تنجم زادة تحط الnotes ولا الslides متاعك في Documents، ونجاوبك منهم.",
    },
    "doc_from": {
        "en": 'From your document "{title}", page {page}: {excerpt} [F1]',
        "fr": "D'après ton document « {title} », page {page} : {excerpt} [F1]",
        "tn": "من الdocument متاعك « {title} »، page {page} : {excerpt} [F1]",
    },
    "doc_more": {
        "en": " Page {page} says more [F2].",
        "fr": " La page {page} en dit plus [F2].",
        "tn": " الpage {page} فيها أكثر [F2].",
    },
    "doc_covers": {
        "en": 'Your document "{title}" covers it on page {page}: {excerpt} [F1]',
        "fr": "Ton document « {title} » en parle page {page} : {excerpt} [F1]",
        "tn": "الdocument متاعك « {title} » يحكي عليها في page {page} : {excerpt} [F1]",
    },
    "notes_from": {
        "en": "From your notes ({sid}, {stitle}): {passage} [{ref}]",
        "fr": "D'après tes notes ({sid}, {stitle}) : {passage} [{ref}]",
        "tn": "من الnotes متاعك ({sid}، {stitle}) : {passage} [{ref}]",
    },
    "mixup": {
        "en": " The mix-up I see most in your answers: {text} [{ref}]. ",
        "fr": " La confusion que je vois le plus dans tes réponses : {text} [{ref}]. ",
        "tn": " الغلطة اللي نشوفها برشا في الأجوبة متاعك : {text} [{ref}]. ",
    },
    "builds": {
        "en": " It builds on {name}, which is still shaky [{ref}], so that's worth a look first.",
        "fr": " Ça repose sur « {name} », qui est encore fragile [{ref}] : ça vaut le coup d'y "
        "jeter un œil d'abord.",
        "tn": " هاذي مبنية على « {name} »، اللي مازالت موش ثابتة [{ref}]، يستاهل تراجعها قبل.",
    },
    "offer": {
        "en": " Want five questions on it?",
        "fr": " Tu veux cinq questions là-dessus ?",
        "tn": " تحب خمسة أسئلة عليها ؟",
    },
    "no_pattern": {
        "en": "I haven't seen a pattern in your wrong answers yet. A few quizzes and I'll be able "
        "to tell a slip from a real mix-up.",
        "fr": "Je n'ai pas encore vu de schéma dans tes erreurs. Encore quelques quiz et je saurai "
        "faire la différence entre une étourderie et une vraie confusion.",
        "tn": "مازلت ما شفتش حاجة تتعاود في الغلطات متاعك. شوية quiz أخرين ونعرف نفرّق بين "
        "غلطة سهو وغلطة فهم.",
    },
    "most": {
        "en": "The mix-up I see most: {text}, {count} times on {concept}, {confident} of them "
        "when you were sure [F1]. ",
        "fr": "La confusion que je vois le plus : {text}, {count} fois en « {concept} », dont "
        "{confident} quand tu étais sûr [F1]. ",
        "tn": "الغلطة اللي نشوفها برشا : {text}، {count} مرات في « {concept} »، منهم {confident} "
        "وانت متأكد [F1]. ",
    },
    "next": {
        "en": " Next: {text} [F2].",
        "fr": " Ensuite : {text} [F2].",
        "tn": " ومن بعد : {text} [F2].",
    },
    "and": {"en": "{a} and {b}", "fr": "{a} et {b}", "tn": "{a} و {b}"},
}


def _say(key: str, **values: object) -> str:
    return _SAY[key][i18n.current()].format(**values)


def _passage(course: Course, concept: Concept) -> str:
    """The lines of the notes about this concept: the section's opening lines."""
    return _sentences(course.section(concept.section).text, 3)


async def _from_documents(
    ctx: LodestarContext, question: str, concept: Concept | None
) -> list[PassageHit]:
    """The student's own passages that answer the question (RAG): hybrid search over their
    uploads, filtered by user. Passages tagged with the concept come first."""
    memory = ctx.services.memory
    if memory is None:
        return []
    query = question if question.strip() else (concept.name if concept else "")
    if concept is not None and concept.name.lower() not in query.lower():
        query = f"{query} {concept.name}"
    try:
        hits = await memory.search_documents(
            ctx.user_id, query, limit=6, doc_id=library.requested_document(question)
        )
        from sqlalchemy import select

        from backend.db import tables as t

        async with ctx.services.engine.connect() as conn:
            allowed = set(
                (
                    await conn.execute(
                        select(t.documents.c.doc_id).where(
                            t.documents.c.user_id == ctx.user_id,
                            t.documents.c.review_required.is_(False),
                        )
                    )
                ).scalars()
            )
        hits = [h for h in hits if UUID(h.doc_id) in allowed]
    except Exception:  # search down: answer from the course notes alone
        return []
    if concept is not None:
        hits.sort(key=lambda h: concept.id not in h.concepts)
    return hits[:DOC_PASSAGES]


def _excerpt(text: str, limit: int = 420) -> str:
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    end = safe_cut(flat, limit)
    return flat[:end].rstrip() + "…"


def _doc_facts(hits: list[PassageHit], start: int = 1) -> list[Fact]:
    return [
        Fact(
            id=f"F{start + i}",
            text=f'Your document "{h.title}", page {h.page}: {_excerpt(h.text)}',
        )
        for i, h in enumerate(hits)
    ]


def _sources(hits: list[PassageHit]) -> list[dict[str, Any]]:
    return [{"title": h.title, "page": h.page, "text": h.text} for h in hits]


async def teach(
    ctx: LodestarContext, state: LodestarState, call: ToolCall
) -> tuple[ToolOutcome, dict[str, Any]]:
    """ "I don't get Bayes": the student's own pages on it first (retrieved from their uploads),
    then the course notes, where they stand, their usual mistake on it, and a shaky prerequisite
    if there is one. A question that matches no concept is answered from their documents alone,
    so any uploaded course works."""
    args = TeachArgs.model_validate(call.args)
    registry = ctx.services.registry
    course = registry.course if registry.courses else None
    concept = (
        course.concept(args.dim)
        if course is not None and args.dim is not None and registry.course_of(args.dim)
        else None
    )
    hits = await _from_documents(ctx, args.question, concept)

    if concept is None or course is None:
        if not hits:
            reply = which_concept(course) if course is not None else _say("no_course")
            reply += _say("also_upload")
            return ToolOutcome(name="teach", reply=reply), {}
        facts = _doc_facts(hits)
        emit(
            {
                "kind": "card",
                "card": "sources",
                "question": args.question,
                "sources": _sources(hits),
            }
        )
        first = hits[0]
        excerpt = _excerpt(first.text, 300)
        text = _say("doc_from", title=first.title, page=first.page, excerpt=excerpt)
        if len(hits) > 1:
            text += _say("doc_more", page=hits[1].page)
        instruction = (
            f'The user asked: "{args.question}". Answer in at most 5 sentences using only these '
            "passages from their own document, citing each one you use. If the passages don't "
            "answer it, say so plainly. Add no fact, formula or number that isn't in them."
        )
        return ToolOutcome(
            name="teach", facts=FactsPacket(facts=facts), instruction=instruction, fallback=text
        ), {}

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

    facts = _doc_facts(hits)
    notes_ref = f"F{len(facts) + 1}"
    facts += [
        Fact(id=notes_ref, text=f"Notes {section.id}, {section.title}: {passage}", dim=concept.id),
        Fact(
            id=f"F{len(facts) + 2}",
            text=f"Key ideas: {'; '.join(concept.key_ideas)}.",
            dim=concept.id,
        ),
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
            "sources": _sources(hits),
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
    if hits:
        first = hits[0]
        excerpt = _excerpt(first.text, 260)
        text = _say("doc_covers", title=first.title, page=first.page, excerpt=excerpt)
    else:
        text = _say(
            "notes_from", sid=section.id, stitle=section.title, passage=passage, ref=notes_ref
        )
    if mistake is not None:
        ref = next(f.id for f in facts if f.text.startswith("Usual mix-up"))
        text += _say("mixup", text=_first_lower(mistake.text), ref=ref)
        text += mistake.fix
    if gap is not None:
        ref = facts[-1].id
        text += _say("builds", name=course.concept(gap.prereq).name.lower(), ref=ref)
    text += _say("offer")
    instruction = (
        f'The user asked: "{args.question}". Explain {concept.name.lower()} in plain words using '
        "only the passages from their own documents, the course notes and the key ideas in the "
        "facts, citing them (their own pages first), in at most 5 sentences. If a fact names their "
        "usual mix-up, say it and the fix. If a fact says it builds on a shaky concept, say so. "
        "End by offering five questions. Add no formula, number or example that isn't in the facts."
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
                    concept_name=_say("and", a=k.concept_name, b=m.concept_name.lower()),
                    count=k.count + m.count,
                    confident=k.confident + m.confident,
                )
            else:
                merged[m.id] = m
        found = sorted(merged.values(), key=lambda m: -m.count)
    if not found:
        return ToolOutcome(name="mistakes", reply=_say("no_pattern")), {}
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
    text = _say(
        "most",
        text=_first_lower(first.text),
        count=first.count,
        concept=first.concept_name.lower(),
        confident=first.confident,
    )
    text += first.fix
    if len(top) > 1:
        text += _say("next", text=_first_lower(top[1].text))
    instruction = (
        f'The user asked: "{args.question}". Name their most frequent mix-up and its fix from the '
        "facts, then the next one, in at most 4 sentences. Say that being sure and wrong is "
        "normal for a mix-up and that the fix is worth reading once."
    )
    return ToolOutcome(
        name="mistakes", facts=FactsPacket(facts=facts), instruction=instruction, fallback=text
    ), {}
