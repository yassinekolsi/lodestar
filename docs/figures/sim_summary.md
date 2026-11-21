# Simulator results (200 users, 10 sessions, seed 2026)

| Experiment | Result | Target | Pass |
|---|---|---|---|
| 1. Recovery r after 10 sessions (mean over 12 concepts) | 0.844 | > 0.8 | yes |
| 2. 80% ranges containing the true skill (sessions 3 and 10) | 0.830 | 0.75-0.85 | yes |
| 3. Achieved success in Balanced mode | 0.800 | 0.8 +/- 0.05 | yes |
| 4. Mean sigma after placement, worst core concept | 0.858 | < 0.9 | yes |
| 5. Bad-data detection precision / recall | 1.00 / 1.00 | > 0.9 / > 0.8 | yes |

Recovery r by session: after 1: 0.671, after 3: 0.666, after 10: 0.844

| Skill | r after 3 | r after 10 | RMSE after 10 | practised by 3 |
|---|---|---|---|---|
| sample_space | 0.671 | 0.878 | 0.542 | 100% |
| counting | 0.649 | 0.848 | 0.553 | 100% |
| equally_likely | 0.657 | 0.824 | 0.588 | 100% |
| addition_rule | 0.639 | 0.824 | 0.580 | 100% |
| conditional | 0.617 | 0.837 | 0.580 | 100% |
| independence | 0.672 | 0.839 | 0.602 | 100% |
| total_probability | 0.639 | 0.844 | 0.593 | 100% |
| bayes | 0.697 | 0.840 | 0.564 | 100% |
| random_variables | 0.736 | 0.868 | 0.561 | 100% |
| expectation | 0.666 | 0.841 | 0.615 | 100% |
| variance | 0.664 | 0.846 | 0.554 | 100% |
| binomial | 0.682 | 0.835 | 0.600 | 100% |

Success in Balanced mode by ability third (low, middle, high): 0.771, 0.811, 0.817 over 3056 rounds.
