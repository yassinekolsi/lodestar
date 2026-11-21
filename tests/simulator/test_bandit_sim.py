"""The course-format experiment reports a paired difference with uncertainty.

The current course has not demonstrated a gain over random format choice. A negative experiment
is a valid result; the test checks the report rather than assert the retired catalog's uplift.
"""

from backend.registry.loader import load_registry
from simulator.bandit import compare


def test_format_comparison_reports_a_valid_paired_interval() -> None:
    c = compare(load_registry(), first_users=600, users=200, sessions=30)
    assert c.users == 200 and c.sessions == 30
    assert c.random_gain > 0 and c.bandit_gain > 0
    difference = c.bandit_gain - c.random_gain
    assert c.diff_low <= difference <= c.diff_high
    assert 0 <= c.share_better <= 1
    assert c.bandit_wins == (c.diff_low > 0)
