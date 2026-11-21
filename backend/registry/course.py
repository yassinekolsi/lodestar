"""A course (docs/plan/19): its notes, the concepts the profile tracks, how they depend on each
other, the usual misconceptions and the question bank. Validated when the registry loads.

Concepts become dimensions and every concept gets two exercises, a quiz and an explain-it-back,
so scoring, planning, "why" and forecasts work on a course exactly as they do on any skill."""

from typing import Any

from pydantic import Field, HttpUrl, model_validator

from backend.contracts.common import Contract, DimensionId

QUIZ_PREFIX = "quiz_"
EXPLAIN_PREFIX = "explain_"
# Answers count only for the concept they test. Prerequisites are handled by the gap rule
# (backend/agent/learning.py): a failed Bayes question says little about sample spaces.
QUIZ_RUSHED_MS = 2500.0  # reading a question and four options takes longer than this


class Misconception(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    text: str = Field(description="The mistake, in plain words")
    fix: str = Field(description="What to do instead, written by the team")


class QuizOption(Contract):
    text: str
    correct: bool = False
    misconception: str | None = None


class Question(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    level: float = Field(ge=0.0, le=1.0)
    stem: str
    options: list[QuizOption] = Field(min_length=2)
    explain: str

    @model_validator(mode="after")
    def _one_answer(self) -> Question:
        if sum(o.correct for o in self.options) != 1:
            raise ValueError(f"{self.id}: exactly one option must be correct")
        if any(o.correct and o.misconception for o in self.options):
            raise ValueError(f"{self.id}: the right answer can't carry a misconception")
        return self

    @property
    def answer(self) -> int:
        return next(i for i, o in enumerate(self.options) if o.correct)


class Section(Contract):
    id: str
    title: str
    text: str


class Concept(Contract):
    id: DimensionId
    name: str
    plain: str
    aliases: list[str] = Field(default_factory=list, description="Words students use for it")
    section: str
    requires: list[DimensionId] = Field(default_factory=list)
    key_ideas: list[str] = Field(min_length=2)
    misconceptions: list[Misconception] = Field(default_factory=list)
    questions: list[Question] = Field(min_length=3)

    @model_validator(mode="after")
    def _tags_known(self) -> Concept:
        known = {m.id for m in self.misconceptions}
        for q in self.questions:
            for o in q.options:
                if o.misconception and o.misconception not in known:
                    raise ValueError(f"{q.id}: unknown misconception {o.misconception}")
        return self

    def misconception(self, misconception_id: str) -> Misconception | None:
        return next((m for m in self.misconceptions if m.id == misconception_id), None)


class CourseSource(Contract):
    title: str
    url: HttpUrl
    license: str


class Course(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    audience: str
    source: CourseSource
    sections: list[Section] = Field(min_length=1)
    concepts: list[Concept] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> Course:
        ids = [c.id for c in self.concepts]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.id}: duplicate concept ids")
        sections = {s.id for s in self.sections}
        questions = [q.id for c in self.concepts for q in c.questions]
        if len(questions) != len(set(questions)):
            raise ValueError(f"{self.id}: duplicate question ids")
        order = {c: i for i, c in enumerate(ids)}
        for c in self.concepts:
            if c.section not in sections:
                raise ValueError(f"{c.id}: unknown section {c.section}")
            for r in c.requires:
                # Listing prerequisites first rules out cycles and keeps the map readable.
                if r not in order or order[r] >= order[c.id]:
                    raise ValueError(f"{c.id}: prerequisite {r} must be an earlier concept")
        return self

    def concept(self, concept_id: str) -> Concept:
        return next(c for c in self.concepts if c.id == concept_id)

    def section(self, section_id: str) -> Section:
        return next(s for s in self.sections if s.id == section_id)

    def localized(self, overlay: dict[str, Any]) -> Course:
        """This course with its text replaced by a translation (registry/courses/i18n/). The
        overlay holds text only, keyed by id: names, notes, key ideas, questions, options,
        explanations and misconceptions. Ids, levels, answers, tags and prerequisites stay the
        course's own, so scoring and the profile are the same in every language. Anything the
        overlay leaves out stays in the original language."""
        sections = overlay.get("sections", {})
        concepts = overlay.get("concepts", {})

        def section(s: Section) -> Section:
            o = sections.get(s.id, {})
            return s.model_copy(update={k: o[k] for k in ("title", "text") if k in o})

        def question(q: Question, o: dict[str, Any]) -> Question:
            update: dict[str, Any] = {k: o[k] for k in ("stem", "explain") if k in o}
            if "options" in o:
                texts = list(o["options"])
                if len(texts) != len(q.options):
                    raise ValueError(f"{q.id}: the translation has {len(texts)} options")
                update["options"] = [
                    opt.model_copy(update={"text": str(t)})
                    for opt, t in zip(q.options, texts, strict=True)
                ]
            return q.model_copy(update=update)

        def misconception(m: Misconception, o: dict[str, Any]) -> Misconception:
            return m.model_copy(update={k: o[k] for k in ("text", "fix") if k in o})

        def concept(c: Concept) -> Concept:
            o = concepts.get(c.id, {})
            update: dict[str, Any] = {k: o[k] for k in ("name", "plain") if k in o}
            if "key_ideas" in o:
                if len(o["key_ideas"]) != len(c.key_ideas):
                    raise ValueError(f"{c.id}: the translation changes the number of key ideas")
                update["key_ideas"] = list(o["key_ideas"])
            # Aliases add up: a French or Derja speaker may still type the English name.
            update["aliases"] = [*c.aliases, *o.get("aliases", [])]
            ms = o.get("misconceptions", {})
            update["misconceptions"] = [
                misconception(m, ms.get(m.id, {})) for m in c.misconceptions
            ]
            qs = o.get("questions", {})
            update["questions"] = [question(q, qs.get(q.id, {})) for q in c.questions]
            return c.model_copy(update=update)

        update: dict[str, Any] = {
            "sections": [section(s) for s in self.sections],
            "concepts": [concept(c) for c in self.concepts],
        }
        for key in ("name", "audience"):
            if key in overlay:
                update[key] = overlay[key]
        return self.model_copy(update=update)

    def chapter(self, concept: Concept) -> str:
        return f"chapter_{concept.section.split('.')[0]}"

    def ancestors(self, concept_id: str) -> list[str]:
        """Every concept this one builds on, nearest first."""
        out: list[str] = []
        frontier = list(self.concept(concept_id).requires)
        while frontier:
            c = frontier.pop(0)
            if c not in out:
                out.append(c)
                frontier.extend(self.concept(c).requires)
        return out

    def dependents(self, concept_id: str) -> list[str]:
        return [c.id for c in self.concepts if concept_id in c.requires]

    def find_question(self, question_id: str) -> tuple[Concept, Question] | None:
        for c in self.concepts:
            for q in c.questions:
                if q.id == question_id:
                    return c, q
        return None

    # What the rest of the registry sees ---------------------------------------------------

    def dimension_entries(self) -> list[dict[str, Any]]:
        return [
            {
                "id": c.id,
                "name": c.name,
                "plain": c.plain,
                "badge": "established",
                "in_overall": True,
                "group": self.chapter(c),
                "framework": [self.name],
                "main_metric": "accuracy",
                "biases": [
                    "With four options, a guess is right one time in four; rounds that look like "
                    "guessing are tested against chance before they count.",
                    "A question can test reading as much as the concept; each concept is checked "
                    "with several questions and an explanation in the student's own words.",
                ],
                "note": f"{self.name}, notes section {c.section}.",
                "sources": [str(self.source.url)],
            }
            for c in self.concepts
        ]

    def game_entries(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for c in self.concepts:
            difficulty = {"difficulty": {"easy": 0.0, "hard": 1.0}}
            out.append(
                {
                    "id": f"{QUIZ_PREFIX}{c.id}",
                    "name": f"Quiz: {c.name}",
                    "kind": "game",
                    "phase": "P1",
                    "dims": {c.id: 1.0},
                    "origin": "original",
                    "reliability": 0.9,
                    "paradigm": "Multiple-choice questions from the course, misconceptions tagged",
                    "code_source": "own",
                    "does": f"Answer questions on {c.name[0].lower()}{c.name[1:]}",
                    "scoring": "binary",
                    "duration_s": 180,
                    "metrics": ["accuracy"],
                    "knobs": difficulty,
                    "level_map": "linear",
                    "content": "code",
                    "modalities": ["keyboard", "touch"],
                    "acs_hooks": ["autonomy"],
                    "practice_trials": 0,
                    "available": True,
                    "terminal": True,
                    "plugin": "quiz",
                    "chance": 0.25,
                    "rushed_ms": QUIZ_RUSHED_MS,
                }
            )
            out.append(
                {
                    "id": f"{EXPLAIN_PREFIX}{c.id}",
                    "name": f"Explain it back: {c.name}",
                    "kind": "game",
                    "phase": "P2",
                    "dims": {c.id: 1.0},
                    "origin": "original",
                    "reliability": 0.4,
                    "paradigm": "Explaining a concept in your own words (teach-back)",
                    "code_source": "own",
                    "does": f"Explain {c.name[0].lower()}{c.name[1:]} in your own words",
                    "scoring": "rubric",
                    "duration_s": 180,
                    "metrics": ["rubric_score"],
                    "knobs": difficulty,
                    "level_map": "linear",
                    "content": "code",
                    "modalities": ["keyboard", "touch", "voice"],
                    "acs_hooks": ["clarification"],
                    "practice_trials": 0,
                    "available": True,
                    "terminal": True,
                    "plugin": "explain",
                    "rushed_ms": 5000.0,
                }
            )
        return out


def concept_of(game_id: str) -> str | None:
    """The concept a course exercise is about, from its id."""
    for prefix in (QUIZ_PREFIX, EXPLAIN_PREFIX):
        if game_id.startswith(prefix):
            return game_id[len(prefix) :]
    return None
