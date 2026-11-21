from datetime import UTC, datetime, timedelta
from uuid import uuid4

import numpy as np
import pytest

from backend.contracts.trial import TrialEvent
from backend.registry.loader import load_registry
from backend.registry.models import Registry
from backend.scoring.kalman_elo import Belief
from backend.scoring.loadings import loading_matrix, update_weight
from backend.scoring.quality import device_lag
from backend.scoring.rounds import RoundOutcome, observed_score, score_round

T0 = datetime(2026, 10, 21, 20, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def registry() -> Registry:
    return load_registry()


def _trials(
    game_id: str, results: list[bool], rt: float = 6000.0, practice: int = 0
) -> list[TrialEvent]:
    round_id, session_id = uuid4(), uuid4()
    return [
        TrialEvent(
            trial_id=uuid4(),
            round_id=round_id,
            session_id=session_id,
            game_id=game_id,
            level=0.4,
            trial_index=i,
            practice=i < practice,
            stimulus={},
            correct=c,
            rt_ms=rt,
            ts=T0 + timedelta(seconds=5 * i),
        )
        for i, c in enumerate(results)
    ]


def _beliefs(registry: Registry, game_id: str) -> dict[str, Belief]:
    return {d: Belief() for d in loading_matrix(registry)[game_id]}


def test_loading_matrix_skips_style_and_calibration(registry: Registry) -> None:
    matrix = loading_matrix(registry)
    assert "balloon_pump" not in matrix and "how_sure" not in matrix
    assert matrix["quiz_counting"] == {"counting": 1.0}


def test_good_round_raises_mu_and_lowers_sigma(registry: Registry) -> None:
    game = registry.game("quiz_conditional")
    out = score_round(
        game,
        _trials("quiz_conditional", [True] * 10 + [False] * 2),
        _beliefs(registry, "quiz_conditional"),
        loading_matrix(registry)["quiz_conditional"],
    )
    wm = out.beliefs["conditional"]
    assert wm.mu > 0 and wm.sigma < 1.5 and wm.n == 12
    assert wm.last_practised == T0 + timedelta(seconds=55)


def test_practice_trials_do_not_count(registry: Registry) -> None:
    game = registry.game("quiz_conditional")
    trials = _trials("quiz_conditional", [True] * 3 + [False] * 10, practice=3)
    out = score_round(
        game,
        trials,
        _beliefs(registry, "quiz_conditional"),
        loading_matrix(registry)["quiz_conditional"],
    )
    assert out.observations == 10 and out.beliefs["conditional"].mu < 0


def test_secondary_loading_moves_less(registry: Registry) -> None:
    game = registry.game("quiz_conditional").model_copy(
        update={"dims": {"conditional": 1.0, "addition_rule": 0.5}}
    )
    out = score_round(
        game,
        _trials(game.id, [True] * 12),
        {"conditional": Belief(), "addition_rule": Belief()},
        game.dims,
    )
    assert out.beliefs["conditional"].mu > out.beliefs["addition_rule"].mu > 0


def test_untrusted_round_changes_nothing(registry: Registry) -> None:
    game = registry.game("quiz_conditional")
    beliefs = _beliefs(registry, "quiz_conditional")
    cheat = _trials("quiz_conditional", [True] * 12, rt=90.0)
    out = score_round(game, cheat, beliefs, loading_matrix(registry)["quiz_conditional"])
    assert out.quality.verdict == "impossible_speed"
    assert out.observations == 0
    assert all(
        out.beliefs[d].mu == b.mu and out.beliefs[d].n == b.n and out.beliefs[d].sigma >= b.sigma
        for d, b in beliefs.items()
    )


def test_life_context_halves_the_update(registry: Registry) -> None:
    """UW9: rounds inside a flagged window move mu about half as much."""
    game = registry.game("quiz_conditional")
    trials = _trials("quiz_conditional", [True] * 9 + [False])
    loads = loading_matrix(registry)["quiz_conditional"]
    start = {"conditional": Belief(mu=0.0, sigma=0.6)}
    full = score_round(game, trials, start, loads).beliefs["conditional"].mu
    half = score_round(game, trials, start, loads, context_weight=0.5).beliefs["conditional"].mu
    assert 0.4 < half / full < 0.65


def test_hshs_game_uses_deadline_from_knobs(registry: Registry) -> None:
    from backend.registry.models import Knob

    game = registry.game("quiz_independence").model_copy(
        update={"scoring": "hshs", "knobs": {"deadline_ms": Knob(easy=1000, hard=1000)}}
    )
    fast, slow = (
        _trials("quiz_independence", [True], rt=300)[0],
        _trials("quiz_independence", [True], rt=1500)[0],
    )
    assert observed_score(game, fast) == 1.0
    assert observed_score(game, slow) == 0.0  # right but slower than this level's pace


def test_anticipations_are_dropped(registry: Registry) -> None:
    game = registry.game("quiz_sample_space")
    trial = _trials("quiz_sample_space", [True], rt=100)[0]
    assert observed_score(game, trial) is None


def test_weights_validate_inputs() -> None:
    assert update_weight(1.0, 0.8, 0.5, 1.0) == pytest.approx(0.4)
    with pytest.raises(ValueError):
        update_weight(1.2, 1, 1, 1)


def test_practice_credit_is_the_lumosity_gain_and_bad_data_gets_none() -> None:
    """The prediction step (registry/practice.yaml): after a round the mean moves up by the
    average gain people make with that much practice; rejected rounds change nothing."""
    registry = load_registry()
    from backend.registry.models import PerRoundGain

    assert registry.practice is None  # no cognitive-game gain is assumed for course mastery
    per_round = PerRoundGain(a=0.1, b=0.5)  # explicit synthetic input to the generic scorer
    assert per_round.gain(2) > per_round.gain(10) > 0
    game = registry.game("quiz_conditional")
    loads = loading_matrix(registry)["quiz_conditional"]
    trials = _trials("quiz_conditional", [True] * 8 + [False] * 4)
    plain = score_round(game, trials, _beliefs(registry, "quiz_conditional"), loads)
    with_credit = score_round(
        game, trials, _beliefs(registry, "quiz_conditional"), loads, practice=per_round
    )
    for dim, loading in loads.items():
        moved = with_credit.beliefs[dim].mu - plain.beliefs[dim].mu
        assert moved == pytest.approx(loading * per_round.gain(1.0))
        assert with_credit.beliefs[dim].sigma == plain.beliefs[dim].sigma
    cheat = [t.model_copy(update={"rt_ms": 80.0}) for t in _trials("quiz_conditional", [True] * 12)]
    rejected = score_round(
        game, cheat, _beliefs(registry, "quiz_conditional"), loads, practice=per_round
    )
    assert rejected.quality.trust == 0
    assert all(rejected.beliefs[d].mu == 0 and rejected.beliefs[d].n == 0 for d in loads)


@pytest.mark.parametrize("lag", [50.0, 100.0, 150.0])
def test_device_lag_is_calibrated_and_removed(registry: Registry, lag: float) -> None:
    """Experiment 6 in docs/plan/15: with 50-150 ms of injected lag, tap-in-time recovers it
    (human tapping noise sd 40 ms); then a lagged honest round scores like an unlagged one and
    a lagged cheater is still caught."""
    rng = np.random.default_rng(int(lag))
    estimate = device_lag(list(lag + rng.normal(0, 40, 8)))
    assert abs(estimate - lag) < 35
    assert device_lag([lag] * 3) == 0.0 and device_lag([900.0] * 8) == 250.0
    from backend.registry.models import Knob

    game = registry.game("quiz_sample_space").model_copy(
        update={
            "scoring": "hshs",
            "rushed_ms": 350,
            "knobs": {"deadline_ms": Knob(easy=1000, hard=1000)},
        }
    )
    loads = loading_matrix(registry)["quiz_sample_space"]

    def play(rt: float, lag_ms: float = 0.0) -> RoundOutcome:
        trials = _trials("quiz_sample_space", [True] * 12, rt=rt)
        return score_round(game, trials, _beliefs(registry, game.id), loads, device_lag_ms=lag_ms)

    honest = play(450).beliefs["sample_space"].mu
    assert play(450 + lag, estimate).beliefs["sample_space"].mu == pytest.approx(honest)
    assert play(120 + lag, estimate).quality.verdict == "impossible_speed"
    if lag == 150:  # uncalibrated, the same lag would cost an honest player and hide a cheater
        assert play(450 + lag).beliefs["sample_space"].mu < honest - 1
        assert play(120 + lag).quality.verdict == "ok"
