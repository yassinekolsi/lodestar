"""Read models for a course (docs/plan/19): the concept map a student sees, and the class view a
teacher sees. Neither carries quiz answers; the class view carries no names."""

import datetime as dt
from typing import Literal

from pydantic import Field

from backend.contracts.common import Contract, DimensionId

ConceptState = Literal["not_checked", "solid", "shaky", "struggling"]


class SectionView(Contract):
    id: str
    title: str
    text: str


class ConceptStatus(Contract):
    id: DimensionId
    name: str
    plain: str
    section: str
    chapter: str
    requires: list[DimensionId]
    key_ideas: list[str]
    n: int = Field(description="Answers that counted")
    percent: float | None = Field(description="Mastery: chance of a typical question right")
    low: float | None
    high: float | None
    state: ConceptState
    plateau: bool = False
    review_due: bool = False
    blocking: list[DimensionId] = Field(
        default_factory=list, description="Struggling concepts this one is the gap under"
    )
    mistake: str | None = Field(default=None, description="Most frequent mix-up on it")
    mistakes: int = 0


class GapView(Contract):
    concept: DimensionId
    prereq: DimensionId
    chain: list[DimensionId]


class CourseMapView(Contract):
    course: str
    name: str
    audience: str
    source_title: str
    source_url: str
    concepts: list[ConceptStatus]
    sections: list[SectionView]
    gap: GapView | None = None
    exam: dt.date | None = Field(default=None, description="The nearest exam goal's date")


class ClassConcept(Contract):
    id: DimensionId
    name: str
    chapter: str
    section: str
    students: int = Field(description="Students with at least one counted answer on it")
    median_percent: float | None
    struggling: int = Field(description="Students below the struggling line (45%)")
    solid: int = Field(description="Students at 70% or more")


class ClassMistake(Contract):
    concept: DimensionId
    concept_name: str
    id: str
    text: str
    fix: str
    students: int
    count: int
    confident: int


class ClassView(Contract):
    course: str
    students: int
    active_week: int = Field(description="Studied in the last 7 days")
    drifting: int = Field(description="Studied before, nothing in the last 7 days")
    concepts: list[ClassConcept]
    mistakes: list[ClassMistake]
    suggestions: list[str] = Field(description="What to revisit in class, in plain words")
