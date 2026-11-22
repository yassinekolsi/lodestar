# Simulator results (200 users, 10 sessions, seed 2026)

| Experiment | Result | Target | Pass |
|---|---|---|---|
| 1. Recovery r after 10 sessions (mean over 16 concepts) | 0.833 | > 0.8 | yes |
| 2. 80% ranges containing the true skill (sessions 3 and 10) | 0.847 | 0.75-0.85 | yes |
| 3. Achieved success in Balanced mode | 0.778 | 0.8 +/- 0.05 | yes |
| 4. Mean sigma after placement, worst core concept | 0.855 | < 0.9 | yes |
| 5. Bad-data detection precision / recall | 1.00 / 1.00 | > 0.9 / > 0.8 | yes |

Recovery r by session: after 1: 0.681, after 3: 0.686, after 10: 0.833

| Skill | r after 3 | r after 10 | RMSE after 10 | practised by 3 |
|---|---|---|---|---|
| sample_space | 0.720 | 0.810 | 0.628 | 100% |
| counting | 0.728 | 0.859 | 0.535 | 100% |
| equally_likely | 0.761 | 0.874 | 0.557 | 100% |
| addition_rule | 0.676 | 0.846 | 0.553 | 100% |
| conditional | 0.636 | 0.842 | 0.616 | 100% |
| independence | 0.705 | 0.811 | 0.657 | 100% |
| total_probability | nan | 0.835 | 0.571 | 0% |
| bayes | 0.640 | 0.810 | 0.577 | 100% |
| random_variables | 0.608 | 0.846 | 0.571 | 100% |
| expectation | 0.682 | 0.792 | 0.645 | 100% |
| variance | nan | 0.823 | 0.625 | 0% |
| binomial | 0.673 | 0.839 | 0.572 | 100% |
| continuous | 0.681 | 0.845 | 0.585 | 100% |
| normal | 0.717 | 0.824 | 0.617 | 100% |
| z_scores | nan | 0.811 | 0.614 | 0% |
| sample_mean | nan | 0.862 | 0.579 | 0% |

Success in Balanced mode by ability third (low, middle, high): 0.742, 0.775, 0.817 over 1384 rounds.
