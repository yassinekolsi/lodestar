"""Experiment 13 (docs/plan/19): does the gap rule find a planted prerequisite gap?

Each simulated student gets one weak concept P (the root). Every concept that builds on P, directly
or not, is held at most a little above it (you can't do Bayes without conditional probability),
and P's own prerequisites are solid. The student then studies for 10 sessions with the real scorer
(simulator/run.py), and Lodestar's `find_gap` (backend/agent/learning.py) is asked where to start.

A hit is `find_gap` naming P. The baseline is what a plain "practise your weakest concept" rule
would pick: the concept with the lowest estimate, which is often one of P's dependents, where
practice can't help until P is fixed.

    python -m simulator.gap_eval --users 200
"""

import argparse
from dataclasses import dataclass

import numpy as np

from backend.agent import learning
from backend.registry.course import Course
from backend.registry.loader import load_registry
from backend.scoring.norms import Norms
from simulator.population import SimUser, make_population
from simulator.run import simulate_user

SESSIONS = 10


@dataclass(frozen=True)
class GapResult:
    students: int
    found: int  # find_gap named the planted root
    baseline: int  # the weakest concept was the planted root
    no_gap: int  # find_gap said nothing
    false_alarms: int  # students with no planted gap where find_gap still named one


def plant(user: SimUser, course: Course, rng: np.random.Generator) -> str:
    """Make one concept the weak root and return it."""
    candidates = [c.id for c in course.concepts if course.dependents(c.id)]
    root = str(rng.choice(candidates))
    weak = float(rng.uniform(-2.2, -1.2))
    user.theta0[root] = weak
    for ancestor in course.ancestors(root):  # what the root builds on is solid
        user.theta0[ancestor] = max(user.theta0[ancestor], float(rng.uniform(0.8, 1.6)))
    for c in course.concepts:
        if root in course.ancestors(c.id):  # what builds on it can't be much better
            user.theta0[c.id] = min(user.theta0[c.id], weak + float(rng.uniform(0.0, 0.6)))
    return root


def evaluate(users: int, seed: int = 2026) -> GapResult:
    registry = load_registry()
    course = registry.course
    norms = Norms()
    rng = np.random.default_rng(seed)
    population = make_population(registry, users, rng, kinds={"normal": 1.0})
    found = baseline = no_gap = 0
    for user in population:
        root = plant(user, course, rng)
        run = simulate_user(user, registry, SESSIONS, rng)
        beliefs = {d: b for d, b in run.beliefs.items() if b.n > 0}
        gap = learning.find_gap(course, beliefs, {}, norms)
        if gap is None:
            no_gap += 1
        elif gap.prereq == root:
            found += 1
        weakest = min(beliefs, key=lambda d: beliefs[d].mu)
        baseline += weakest == root

    # Students with nothing planted: how often does the rule still send them back?
    control = make_population(registry, users, rng, kinds={"normal": 1.0})
    false_alarms = 0
    for user in control:
        # Lift everyone a little so no concept is weak by chance alone.
        for d in user.theta0:
            user.theta0[d] = max(user.theta0[d], 0.5)
        run = simulate_user(user, registry, SESSIONS, rng)
        beliefs = {d: b for d, b in run.beliefs.items() if b.n > 0}
        false_alarms += learning.find_gap(course, beliefs, {}, norms) is not None
    return GapResult(users, found, baseline, no_gap, false_alarms)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", type=int, default=200)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args(argv)
    r = evaluate(args.users, args.seed)
    print("| Check | Result |")
    print("|---|---|")
    print(f"| Planted gap found by the gap rule | {r.found}/{r.students} ({r.found / r.students:.0%}) |")
    print(
        f"| Planted gap found by 'practise your weakest concept' | {r.baseline}/{r.students} "
        f"({r.baseline / r.students:.0%}) |"
    )
    print(f"| No gap named | {r.no_gap}/{r.students} |")
    print(
        f"| Gap named for students with nothing planted (all concepts solid) | "
        f"{r.false_alarms}/{r.students} ({r.false_alarms / r.students:.0%}) |"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
