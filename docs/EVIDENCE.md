# Evidence map

Every claim Lodestar makes, the number behind it, and how to check it yourself. The design is in
[plan/19-study-coach.md](plan/19-study-coach.md).

Reproduce with `make up && make seed` (the app), `make test` (unit tests), `make sim N=200` (the
simulated-student checks) and `python -m simulator.gap_eval --users 200` (the planted-gap
experiment).

## Before you conclude something is missing

| It looks like… | What is actually there | Check |
|---|---|---|
| "The questions are generated, so they may be wrong" | The demo course's 67 questions, 36 misconceptions and their fixes were written and checked by the team. The loader rejects a question without exactly one right answer, an unknown misconception tag, or a prerequisite cycle. | `registry/courses/probability.yaml`, `backend/registry/course.py`, `tests/backend/agent/test_learning.py` |
| "The AI tutor can make things up" | Explanations are built from a facts packet: the notes section, the key ideas, the student's own data. A verifier rejects any number that isn't in a fact; without a model, a template quotes the notes. | `backend/agent/study_tools.py`, `backend/coach/verify.py` |
| "The demo numbers are hand-written" | Every seeded answer is a real course question answered by a simulated student, and every estimate comes from the real scorer fed those answers in order. The plateau, the gap and the recurring misconception are computed, and a test checks all three. | `backend/db/seed.py`, `tests/backend/db/test_seed.py` |
| "Needs a paid AI key" | No. A local Ollama model if one runs, fixed templates otherwise. Every screen of the demo works with neither. | `backend/llm/factory.py` |
| "The gap rule is a heuristic nobody tested" | Experiment 13 plants a weak concept in simulated students: the rule finds it 72% of the time, against 24% for "practise your weakest concept", and fires for 5% of students with nothing planted. | `simulator/gap_eval.py` |
| "No real students" | True for Lodestar itself: a classroom pilot is planned, not done. The engagement model was trained and tested on real students (OULAD). | below |

## The claims

Student uploads are covered by [the library review notes](plan/20-student-library.md) and
`tests/backend/agent/test_documents.py`. Gemini OCR can misread handwritten mathematics even after
a second pass; OCR chapters require approval before study. Formula rendering tests establish
syntax and display behavior, not transcription accuracy. The additional intent regression cases
have informed routing fixes and are no longer an untouched held-out evaluation set.

| Claim | Evidence | Check |
|---|---|---|
| Finds why a concept won't stick | Gap rule: the deepest shaky prerequisite under a concept with low mastery (fairly surely low: the top of its 80% range under 50%). Experiment 13: 72% vs 24%. | `find_gap` in `backend/agent/learning.py`, `simulator/gap_eval.py` |
| Names the misconception behind a wrong answer | 104 of the wrong options are tagged; the quiz shows the mix-up and its fix; the coach's **mistakes** tool counts them per student, and how many were made while sure | `frontend/src/games/quiz/plugin.ts`, `misconception_counts` |
| Explains from the student's own course | **teach** tool: notes section, key ideas, mastery, usual mix-up, shaky prerequisite, all as cited facts | `backend/agent/study_tools.py` |
| Checks understanding, not only recall | Explain it back with a key-idea rubric (low weight, reliability 0.4, shown to the student) | `rubric_score`, `frontend/src/games/explain/plugin.ts` |
| Honest uncertainty | Mastery with an 80% range everywhere; simulated ranges contain the true level 83.0% of the time | `backend/scoring/norms.py`, `make sim` |
| Right difficulty | Balanced mode aims for 80% right; simulated students get 80.0% | `make sim` |
| Comes back before it fades | Review after 1, 2, 5 or 10 days by mastery; uncertainty grows with time away | `review_due_in_days` |
| Doesn't keep drilling what isn't working | Plateau (10 days, 40 answers, no trend) switches to explain it back with a new way to study | `backend/scoring/patterns.py`, `backend/agent/patterns.py` |
| Rushed rounds don't count | Median answer under 2.5 s with low accuracy, or impossibly fast and right: precision and recall 1.00 on simulated clickers and cheaters | `backend/scoring/quality.py`, `make sim` |
| Notices a student drifting away | Engagement model, trained on real students and tested on others: OULAD, 25,273 students, AUC 0.857 | `backend/ml/model_cards/`, `backend/ml/engagement.py` |
| Helps teachers | Class view: per-concept medians and counts, misconceptions by number of students, plain suggestions; no names | `backend/api/course.py` (`/class`) |
| Every choice explained | Every pick carries its reason and the data behind it; every decision is stored with its candidates | `backend/agent/why.py`, `agent.decisions` |

## Simulated students

200 simulated students with known true levels per concept, 5-question quizzes, four a session, 10
sessions, through the real scorer (`make sim N=200`, seed 2026):

| Check | Result | Target |
|---|---|---|
| Recovery of the true level after 10 sessions (mean r over 12 concepts) | 0.844 | > 0.80 |
| Recovery after 1 and 3 sessions | 0.671, 0.666 | reported |
| 80% ranges containing the true level (sessions 3 and 10) | 0.830 | 0.75–0.85 |
| Success in Balanced mode | 0.800 | 0.80 ± 0.05 |
| σ after placement, worst core concept | 0.858 | < 0.9 |
| Clickers and cheaters caught (precision / recall) | 1.00 / 1.00 | > 0.9 / > 0.8 |

The targets of the cognitive-training version assumed 12-answer rounds; for a course, a round is 5
questions, so recovery is judged after 10 sessions (about two weeks) and placement after one quiz
per chapter foundation. The choice and the reason are in `simulator/experiments.py`.

## Safety and data

The experimental format bandit has **not** demonstrated an improvement over random format choice
on the current course catalog. With seed 2026, 600 prior students and 200 comparison students over
30 sessions, true gain was 1.393 for random choice and 1.386 for the bandit; the paired 95% interval
was -0.028 to +0.014, with 45% gaining more under the bandit. Reproduce with
`python -m simulator.bandit --first 600 --users 200 --sessions 30` (it returns failure when the
interval includes zero). The core study planner uses prerequisites, review and plateau rules;
no course-format uplift claim is made.

| Rule | Enforced by |
|---|---|
| No labels about the person in any user-facing text | `make lint-language` in CI; `backend/coach/verify.py` on every reply |
| Quiz answers never reach the browser through the registry | `/registry` strips the courses; the concept map comes from `/course`, without questions |
| The class view never shows a name or one student's answers | `/class` returns counts and medians only |
| Every memory query is filtered by user | `test_search_without_a_user_is_impossible` |
| Delete leaves nothing behind | `test_delete_leaves_nothing_behind` |
| User API keys never leak | `test_export_has_everything_and_never_a_key` |

## What is not done yet

- A pilot with a real class (comprehension of the "why" cards; does the gap rule name the gap a
  teacher would name).
- Courses drafted from uploaded PDFs (concepts, prerequisites, questions and tags by an LLM, checked
  in code and by the teacher).
- An LLM grader for explain it back.
- The growth forecast's coverage on course mastery (it was validated on 36,297 real learners'
  practice curves, not on course data).
- Interfaces in French and Arabic.
