"""Quiz questions from a student's own document (docs/plan/20).

Two ways, both grounded in passages with their page:

- **From the text, by code** (always works, no model): definition sentences ("A random variable
  is a number given to each outcome") become "which term is this?" questions, and sentences that
  use a key term of the course or of the document become fill-the-gap questions. The right answer
  is the word that was in the student's own text, so it can't be wrong; the wrong options are other
  key terms from the same document. Every question cites its page.
- **By a language model** when one is available: it drafts questions from the same passages, and
  code checks each one before it is served (four different options, exactly one answer, a page that
  was given, an explanation taken from the passage). Anything that fails is dropped, and the code
  questions fill the gap.

The output is the quiz plugin's content format (backend/agent/learning.py, quiz_content), so the
same plugin plays it, with "How sure?", hints and feedback.
"""

import hashlib
import random
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

QUESTIONS = 5
LEVEL = 0.45  # questions from notes aren't calibrated yet: middle of the scale

_DEFINITION = re.compile(
    r"^(?:(?:the|a|an)\s+)?(?P<term>[A-Za-z][A-Za-z0-9'() -]{2,48}?)\s+"
    r"(?:is|are|means|refers to|is called|is defined as)\s+(?P<rest>.{20,260})$",
    re.I,
)
_STARTS_BAD = re.compile(r"^(this|that|it|there|here|they|we|you|he|she|which|what|so|but)\b", re.I)


@dataclass(frozen=True)
class Source:
    """A passage a question can come from."""

    text: str
    page: int
    concepts: Sequence[str] = ()


def _sentences(text: str) -> list[str]:
    flat = " ".join(text.split())
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", flat) if 30 <= len(s.strip()) <= 320]


def definitions(sources: Sequence[Source]) -> list[tuple[str, str, Source]]:
    """(term, the rest of the sentence, source) for sentences that define a term."""
    out = []
    seen: set[str] = set()
    for src in sources:
        for s in _sentences(src.text):
            m = _DEFINITION.match(s.rstrip("."))
            if not m or _STARTS_BAD.match(s):
                continue
            term = m.group("term").strip(" -")
            if len(term.split()) > 5 or term.lower() in seen:
                continue
            seen.add(term.lower())
            out.append((term, m.group("rest").strip(), src))
    return out


def key_terms(sources: Sequence[Source], vocabulary: Sequence[str]) -> list[str]:
    """Terms worth asking about: the course vocabulary found in the text, then defined terms."""
    text = " ".join(s.text for s in sources).lower()
    found = [v for v in sorted(set(vocabulary), key=len, reverse=True) if v.lower() in text]
    found += [t for t, _, _ in definitions(sources)]
    out: list[str] = []
    for t in found:
        if not any(t.lower() == o.lower() or t.lower() in o.lower() for o in out):
            out.append(t)
    return out


def _qid(text: str) -> str:
    return "doc_" + hashlib.sha1(text.encode()).hexdigest()[:10]


def _question(
    stem: str, answer: str, distractors: list[str], explain: str, src: Source, rng: random.Random
) -> dict[str, Any]:
    options = [answer, *distractors[:3]]
    rng.shuffle(options)
    right = options.index(answer)
    wrong = [i for i in range(len(options)) if i != right]
    return {
        "id": _qid(stem),
        "level": LEVEL,
        "stem": stem,
        "options": [{"text": o, "misconception": None} for o in options],
        "answer": right,
        "explain": explain,
        "hints": [
            f"It's on page {src.page} of your document.",
            "Two of the wrong answers are gone.",
        ],
        "remove": wrong[:2],
        "fixes": {},
        "page": src.page,
        "concepts": list(src.concepts),
    }


def from_text(
    sources: Sequence[Source], vocabulary: Sequence[str], seed: int, n: int = QUESTIONS
) -> list[dict[str, Any]]:
    """Questions made by code from the student's own sentences. Needs at least four key terms
    (an answer and three wrong options); returns fewer questions, or none, otherwise."""
    rng = random.Random(seed)
    terms = key_terms(sources, vocabulary)
    if len(terms) < 4:
        return []
    out: list[dict[str, Any]] = []
    used: set[str] = set()

    def others(answer: str) -> list[str]:
        pool = [t for t in terms if t.lower() != answer.lower()]
        rng.shuffle(pool)
        return pool[:3]

    defs = definitions(sources)
    rng.shuffle(defs)
    for term, rest, src in defs:
        if len(out) >= (n + 1) // 2:
            break
        stem = f'Which term does your document (page {src.page}) describe as "{rest.rstrip(".")}"?'
        out.append(_question(stem, term, others(term), f"Page {src.page}: {term} {rest}", src, rng))
        used.add(term.lower())

    gaps: list[tuple[str, str, Source]] = []
    for src in sources:
        for s in _sentences(src.text):
            for t in terms:
                if t.lower() in used:
                    continue
                m = re.search(rf"(?<![\w]){re.escape(t)}(?![\w])", s, re.I)
                if m and len(s) - len(t) > 25:
                    gaps.append((t, s, src))
                    break
    rng.shuffle(gaps)
    for term, sentence, src in gaps:
        if len(out) >= n:
            break
        if term.lower() in used:
            continue
        blanked = re.sub(
            rf"(?<![\w]){re.escape(term)}(?![\w])", "_____", sentence, count=1, flags=re.I
        )
        stem = f'Fill the gap, from your document (page {src.page}): "{blanked}"'
        out.append(_question(stem, term, others(term), f"Page {src.page}: {sentence}", src, rng))
        used.add(term.lower())
    return out


# Drafted by a language model, checked by code -------------------------------------------------


class DraftQuestion(BaseModel):
    page: int = Field(description="The page number of the passage the question comes from")
    stem: str = Field(description="The question, answerable from that passage alone")
    options: list[str] = Field(description="Exactly four answer options")
    answer: int = Field(description="Index (0-3) of the one right option")
    explain: str = Field(description="Why the right option is right, quoting the passage")


class DraftQuiz(BaseModel):
    questions: list[DraftQuestion]


PROMPT = """You write multiple-choice questions that check understanding of a student's own course
notes. Use only the passages below. Write {n} questions. Each question: one passage's page number,
a stem answerable from that passage alone, exactly four short options of which exactly one is right,
wrong options that a student who misunderstood the idea might pick, and an explanation that quotes
the passage. No question about page layout or titles.

{passages}"""


def prompt(sources: Sequence[Source], n: int = QUESTIONS) -> str:
    passages = "\n\n".join(f"[page {s.page}]\n{s.text[:1200]}" for s in sources[:8])
    return PROMPT.format(n=n, passages=passages)


def checked(draft: DraftQuiz, sources: Sequence[Source], seed: int) -> list[dict[str, Any]]:
    """Keep only drafted questions that pass the checks, in the quiz plugin's format."""
    rng = random.Random(seed)
    pages = {s.page: s for s in sources}
    out = []
    for q in draft.questions:
        options = [o.strip() for o in q.options]
        if (
            q.page not in pages
            or len(options) != 4
            or len({o.lower() for o in options}) != 4
            or not 0 <= q.answer < 4
            or not q.stem.strip()
            or len(q.explain.strip()) < 15
        ):
            continue
        src = pages[q.page]
        answer = options[q.answer]
        distractors = [o for i, o in enumerate(options) if i != q.answer]
        out.append(_question(q.stem.strip(), answer, distractors, q.explain.strip(), src, rng))
    return out


def as_content(
    questions: list[dict[str, Any]], title: str, doc_id: str, made_by: str
) -> dict[str, Any]:
    pages = sorted({q["page"] for q in questions})
    return {
        "course": "notes",
        "concept": doc_id,
        "concept_name": title,
        "section": {"id": f"p. {', '.join(str(p) for p in pages)}", "title": title},
        "questions": questions,
        "made_by": made_by,
    }
