"""Load and validate the YAML registry."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from backend.config import get_settings
from backend.registry.course import Course
from backend.registry.models import Registry


def _read(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _translations(root: Path, courses: list[Course]) -> dict[str, list[Course]]:
    """registry/courses/i18n/<course>.<locale>.yaml: the text of a course in another language.
    Each translated course is validated like the original (one right answer per question, known
    tags), so a broken translation stops the server at startup, not in front of a student."""
    out: dict[str, list[Course]] = {}
    by_id = {c.id: c for c in courses}
    for path in sorted((root / "courses" / "i18n").glob("*.*.yaml")):
        course_id, locale = path.stem.split(".", 1)
        if course_id not in by_id:
            raise ValueError(f"{path.name}: no course {course_id}")
        translated = by_id[course_id].localized(_read(path) or {})
        out.setdefault(locale, []).append(Course.model_validate(translated.model_dump()))
    return out


def load_registry_from(root: Path) -> Registry:
    games = [_read(p) for p in sorted((root / "games").glob("*.yaml"))]
    dimensions = _read(root / "dimensions.yaml") or []
    courses = [Course.model_validate(_read(p)) for p in sorted((root / "courses").glob("*.yaml"))]
    for course in courses:
        # Concepts are dimensions, and each concept has a quiz and an explain-it-back.
        dimensions += course.dimension_entries()
        games += course.game_entries()
    return Registry.model_validate(
        {
            "dimensions": dimensions,
            "games": games,
            "courses": courses,
            "translations": _translations(root, courses),
            "providers": _read(root / "llm_providers.yaml"),
            "batteries": _read(root / "batteries.yaml"),
            "consent": _read(root / "consent.yaml"),
            "priors": _read(root / "priors.yaml") if (root / "priors.yaml").exists() else None,
            "practice": (
                _read(root / "practice.yaml") if (root / "practice.yaml").exists() else None
            ),
        }
    )


def load_knowledge_items() -> list[dict[str, Any]]:
    """Team-written coaching tips for the shared knowledge collection."""
    items: list[dict[str, Any]] = _read(Path(get_settings().registry_dir) / "knowledge.yaml")
    return items


@lru_cache
def load_registry() -> Registry:
    return load_registry_from(Path(get_settings().registry_dir))
