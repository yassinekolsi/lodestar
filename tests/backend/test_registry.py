import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.api.main import app
from backend.registry.loader import load_registry
from backend.registry.models import Game, Knob, Registry

PLAN_DIMENSIONS = {
    "sample_space",
    "total_probability",
    "variance",
    "independence",
    "conditional",
    "addition_rule",
    "equally_likely",
    "binomial",
    "counting",
    "bayes",
    "random_variables",
    "expectation",
}

# docs/plan/06, "Core set".
PLAN_P1_GAMES = {
    *(f"quiz_{concept}" for concept in PLAN_DIMENSIONS),
}


@pytest.fixture(scope="module")
def registry() -> Registry:
    return load_registry()


# The plan's lists are a floor: a skill or core game added later is a registry edit (WP4.4).
def test_dimensions_include_the_plan(registry: Registry) -> None:
    assert {d.id for d in registry.dimensions} >= PLAN_DIMENSIONS


def test_p1_games_include_the_plan(registry: Registry) -> None:
    assert {g.id for g in registry.games if g.phase == "P1"} >= PLAN_P1_GAMES


def test_core_set_covers_established_skills_except_sustained_attention(
    registry: Registry,
) -> None:
    established = {d.id for d in registry.dimensions if d.badge == "established"}
    covered = {d for g in registry.games if g.phase == "P1" for d in g.primary_dims}
    assert established <= covered


def test_experimental_dimensions_stay_out_of_overall(registry: Registry) -> None:
    for dim in registry.dimensions:
        if dim.badge == "experimental":
            assert not dim.in_overall


def test_uploaded_notes_have_no_fixed_mastery_dimensions(registry: Registry) -> None:
    assert registry.game("quiz_notes").dims == {}


def test_onboarding_battery_uses_core_games(registry: Registry) -> None:
    battery = registry.batteries["onboarding"]
    assert battery.games[0] == "quiz_sample_space"  # also measures device lag (UW1)
    assert all(registry.game(g).phase == "P1" for g in battery.games)
    assert registry.core_skills() == {
        "equally_likely",
        "sample_space",
        "conditional",
        "random_variables",
    }


def test_knobs_move_from_easy_to_hard(registry: Registry) -> None:
    for game in registry.games:
        for name, knob in game.knobs.items():
            assert game.knobs_at(0.0)[name] == knob.easy
            assert game.knobs_at(1.0)[name] == knob.hard
            values = [knob.at(i / 10) for i in range(11)]
            assert values == sorted(values) or values == sorted(values, reverse=True), name


def test_int_knob_rounds_half_up() -> None:
    assert Knob(easy=1, hard=4).at(0.5) == 3.0


def test_reliability_follows_origin(registry: Registry) -> None:
    assert registry.game("quiz_conditional").effective_reliability == 0.9
    assert registry.game("quiz_counting").effective_reliability == 0.9
    assert registry.game("explain_conditional").effective_reliability == 0.4
    assert registry.game("quiz_notes").effective_reliability == 0.5


def test_providers(registry: Registry) -> None:
    hosted = {p.id for p in registry.providers if p.needs_key}
    assert hosted == {
        "anthropic",
        "openai",
        "gemini",
        "deepseek",
        "xai",
        "mistral",
        "groq",
        "openrouter",
    }
    assert not registry.provider("anthropic").capabilities.forced_tool_choice


def _game(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "test_game",
        "name": "Test",
        "kind": "game",
        "phase": "P1",
        "dims": {"bayes": 1.0},
        "origin": "classic",
        "paradigm": "x",
        "code_source": "own",
        "does": "x",
        "scoring": "binary",
        "duration_s": 60,
        "metrics": ["accuracy"],
        "knobs": {"n": {"easy": 1, "hard": 3}},
        "level_map": "linear",
        "content": "code",
        "modalities": ["keyboard"],
        "acs_hooks": [],
        "practice_trials": 3,
    }
    return base | overrides


def test_game_needs_a_primary_dimension() -> None:
    with pytest.raises(ValidationError, match="primary"):
        Game.model_validate(_game(dims={"bayes": 0.5}))


def test_level_map_needs_knobs() -> None:
    with pytest.raises(ValidationError, match="level_map"):
        Game.model_validate(_game(knobs={}))


def test_unknown_dimension_is_rejected(registry: Registry) -> None:
    bad = Game.model_validate(_game(id="bad", dims={"telepathy": 1.0}))
    with pytest.raises(ValidationError, match="unknown dimensions"):
        Registry.model_validate(registry.model_dump() | {"games": [*registry.games, bad]})


def test_registry_endpoint_hides_test_provider(registry: Registry) -> None:
    body = TestClient(app).get("/registry").json()
    assert len(body["dimensions"]) == len(registry.dimensions)
    assert "stub" not in {p["id"] for p in body["providers"]}


def test_every_registered_concept_has_both_browser_formats(registry: Registry) -> None:
    for concept in registry.course.concepts:
        assert registry.game(f"quiz_{concept.id}").available
        assert registry.game(f"explain_{concept.id}").available
