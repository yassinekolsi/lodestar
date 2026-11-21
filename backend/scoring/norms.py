"""From concept estimates to percentages (docs/plan/07, 19). Every percentage comes with its range.

For a course, the percentage is mastery: the chance of getting a typical question on the concept
right, a mid-level question of the course (level 0.5, difficulty b = 0). It needs no population,
so it means the same thing for the first student as for the thousandth. The range comes from the
80% interval of the estimate.
"""

from dataclasses import dataclass
from typing import Literal

from backend.scoring.kalman_elo import Belief, interval, logistic

# A typical question: the middle of the course's difficulty scale (backend/scoring/levels.py).
TYPICAL_B = 0.0


@dataclass(frozen=True)
class Norm:
    typical_b: float = TYPICAL_B
    source: Literal["mastery"] = "mastery"


@dataclass(frozen=True)
class PercentRange:
    value: float  # 0..100
    low: float
    high: float
    source: Literal["mastery"]

    def label(self) -> str:
        return f"{self.value:.0f}% (likely {self.low:.0f}-{self.high:.0f}%)"


class Norms:
    def __init__(self, norms: dict[str, Norm] | None = None) -> None:
        self._norms = norms or {}

    def norm(self, dim: str) -> Norm:
        return self._norms.get(dim, Norm())

    def percentile(self, dim: str, belief: Belief) -> PercentRange:
        """Mastery of a concept, as a percentage with its 80% range."""
        norm = self.norm(dim)
        lo, hi = interval(belief)

        def pct(x: float) -> float:
            return 100.0 * logistic(x - norm.typical_b)

        return PercentRange(pct(belief.mu), pct(lo), pct(hi), norm.source)
