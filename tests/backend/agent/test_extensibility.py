"""A YAML course concept is available to policy, scoring and the student profile."""

import shutil
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.db.twin_store import read_twin
from backend.registry.loader import load_registry_from
from backend.registry.models import Registry
from tests.backend.agent.conftest import RunnerFactory
from tests.backend.agent.test_graph import play
from tests.backend.agent.test_policy import returning_user, start


@pytest.fixture
def extended(tmp_path: Path) -> Registry:
    root = tmp_path / "registry"
    shutil.copytree("registry", root)
    course_file = root / "courses" / "probability.yaml"
    course = yaml.safe_load(course_file.read_text())
    concept = {
        **course["concepts"][-1],
        "id": "extra_concept",
        "name": "Extra concept",
        "aliases": ["extra concept"],
        "requires": ["sample_space"],
    }
    concept["questions"] = [{**q, "id": f"extra_{i}"} for i, q in enumerate(concept["questions"])]
    course["concepts"].append(concept)
    course_file.write_text(yaml.safe_dump(course, sort_keys=False))
    return load_registry_from(root)


def test_yaml_concept_creates_both_exercise_formats(extended: Registry) -> None:
    assert extended.dimension("extra_concept").name == "Extra concept"
    assert extended.game("quiz_extra_concept").primary_dims == ["extra_concept"]
    assert extended.game("explain_extra_concept").plugin_id == "explain"


async def test_new_concept_is_picked_scored_and_shown(
    extended: Registry,
    make_runner: RunnerFactory,
    aengine: AsyncEngine,
) -> None:
    runner = await make_runner()
    runner.services = replace(runner.services, registry=extended)
    user_id = await returning_user(aengine)
    session_id, spec = await start(runner, user_id)
    assert spec["game_id"] == "quiz_extra_concept"
    assert spec["content"]["questions"] and spec["reason"]
    await play(runner, aengine, user_id, session_id, spec, [True] * 8 + [False] * 2)
    async with aengine.connect() as conn:
        twin = await read_twin(conn, user_id)
    concept = next(d for d in twin.dims if d.dim == "extra_concept")
    assert concept.n > 0 and concept.mu > 0 and concept.sigma < 1.5
    assert concept.percent_low < concept.percent < concept.percent_high
