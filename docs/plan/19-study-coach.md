# 19 · Lodestar as a study coach

## The challenge

> How can an AI solution respond to students' difficulties in understanding their courses, enrich
> how they learn, and lastingly improve their educational experience?

Our answer: a study coach that finds **why** a concept isn't sticking, explains it **from the
student's own course**, checks that it stuck, and comes back to it **before it fades**. It never
labels the student, and every number it shows comes with how sure it is.

## What changed from the cognitive-training version

Lodestar started as a coach for thinking skills (attention, memory, reasoning) measured with short
games. The engine underneath was built to be registry-driven, so the pivot keeps it and changes what
it measures:

| Kept as is | Changed |
|---|---|
| Kalman-Elo estimate with an 80% range per skill, drift with time away | A **skill is now a concept** of the course; percentages are **mastery** (chance of a typical question right), not a percentile |
| The LangGraph agent, its 22 nodes, checkpointer, decisions stored with their candidates | `plan_next` gained the **prerequisite-gap** rule, **consolidation** (explain it back after a strong quiz) and **review timing** |
| Facts-packet coach with a verifier (no number without a cited fact) | Two new tools: **teach** (explain a concept from the notes) and **mistakes** (the mix-ups behind wrong answers) |
| Plateau and rushed-round detection, pushback, forecast ranges | Thresholds suited to 5-question quizzes; rushed = median answer under 2.5 s, since a question has to be read |
| Engagement model trained on 25,273 real OULAD students | Now used on the population it was trained on: students |
| Memory, consent, export, delete, choice of AI provider, local fallback, voice, terminal client | Copy, tips and memory notes rewritten for studying |
| — | 43 cognitive games removed; two plugins (quiz, explain it back) play every concept of any course |
| — | A **concept map** replaces the night sky; a **class view** for teachers |

## The course model

`registry/courses/<course>.yaml` holds everything about a course (`backend/registry/course.py`
validates it at start-up):

- **sections**: the course notes, as a student would cite them ("Notes 2.1").
- **concepts**: id, name, the section it lives in, **requires** (its prerequisites; each must be an
  earlier concept, so the map has no cycles), **aliases** (the words students use for it, which
  drive intent routing), **key ideas** (the explain-it-back rubric) and **misconceptions** (each
  with a fix written by the team).
- **questions**: multiple choice with a level from 0 to 1. Every wrong option that matches a known
  misconception carries its tag. Exactly one option is right.

The loader turns each concept into a dimension and two exercises: `quiz_<concept>` (binary scoring,
reliability 0.9, chance 0.25) and `explain_<concept>` (rubric scoring, reliability 0.4). From there
the scorer, the planner, "why", patterns and forecasts treat them like any other skill.

The demo course is **Probability 1**: 12 concepts in three chapters, 67 questions with 104 wrong options tagged, 36 distinct misconceptions
written from the probability-education literature (inverse conditional, base-rate neglect,
gambler's fallacy, mutually exclusive taken as independent, unweighted averaging in total
probability, and others).

## How a session decides

1. **Placement** on the first visit: one quiz per chapter's foundation (`registry/batteries.yaml`).
2. **Prerequisite gap.** A concept with mastery under 45% is *struggling*. Lodestar walks down its
   prerequisites and stops at the deepest one that is *shaky* (mastery under 60%, a range wider
   than 45 points, or never checked), and quizzes that first, saying why: "Bayes' theorem is at
   11% (likely 5-22%), and it builds on conditional probability, which is still shaky: 45%
   (likely 31-58%)." Struggling is judged on mastery, not the share of right answers: the level
   adapts, so a struggling student still gets most of their (easier) questions right.
3. **Plateau.** No trend over 10 days and 40 answers: more quizzes won't help, so the concept moves
   to explain it back, with a different way to study it (by chapter: write out the outcomes; turn
   probabilities into counts with a two-way table; write the distribution as a table).
4. **Consolidate.** After a quiz at 80% or more, explain the same concept back once that session.
5. **Review.** A concept practised long enough ago comes back: after 1 day under 50% mastery, 2
   days under 70%, 5 days under 85%, 10 days above. Uncertainty also grows with time away, which
   raises the concept in the planner's ranking on its own.
6. Otherwise the usual utility: uncertainty, staleness, goals (exam dates), the bandit, fatigue and
   repetition, every part shown in "Why?".

## In a quiz

- Questions near the chosen level, easiest first, not repeated within a week.
- **"How sure?" on every answer** (guessing, fairly sure, sure). A confident wrong answer is usually
  a misconception; an unsure one is usually something not learned yet. Errors made with high
  confidence are the most likely to be corrected once the student sees why (Butterfield & Metcalfe,
  2001), so the feedback says so.
- **Hints**: the first points to the notes, the second removes two wrong answers. An answer found
  with one hint counts 0.75, with two 0.5.
- **Feedback** names the misconception behind a wrong answer and its fix, explains the right
  answer, and cites the notes section.
- Rounds answered faster than anyone can read (median under 2.5 s with low accuracy) don't count.

## Explain it back

The student explains the concept in their own words (typed or spoken). A rule in code checks which
key ideas are present: an idea counts when at least half its content words appear (matched on their
first five letters), scaled down under 25 words. The student sees which ideas they covered. It
counts at low weight (reliability 0.4) because a word rule can be fooled; an LLM grader can replace
it later, verified the same way as the coach.

## Grounded explanations

"I don't get Bayes' theorem" goes to the **teach** tool. Its facts are the notes section, the key
ideas, the student's mastery, their most frequent mix-up on that concept, and a shaky prerequisite
if there is one. The coach may reword these and nothing else: the verifier rejects any number that
isn't in a fact, so a made-up example with new numbers can't get through. Without any model, the
fixed template quotes the notes and the student's own data.

## The AI collaboration score, for studying

- **Autonomy**: a quiz answer right without opening a hint.
- **Verification**: a quiz answer whose "How sure?" matches the outcome (sure and right, or unsure
  and wrong): checking your own work. Pushing back on a result also counts.
- Iteration, clarification and responsible use as before.

## The class view

`GET /class` aggregates everyone studying the course on the server: per concept, the median mastery
and how many students are below 45% or at 70% and above; the misconceptions that appear in the most
students' answers; who hasn't studied in a week. It returns counts only, never names or one
student's answers. It turns these into two or three plain suggestions ("Revisit notes 2.4 (Bayes'
theorem): 13 of 20 students are below 45%, and 'swapping P(A | B) and P(B | A)' shows up in 20
students' answers"). In a school deployment it sits behind a teacher role; the demo lets any
signed-in user open it.

## The demo data

`make seed` creates Alex, five weeks into the course, and 24 classmates. Every answer is a real
question answered by a simulated student with a known true level per concept and habitual
misconceptions, and every estimate comes from the real scorer fed those answers in order. So the
plateau on conditional probability, the gap under Bayes' theorem and the recurring inverse
conditional are what Lodestar computes from the stored answers (`tests/backend/db/test_seed.py`
checks all three).

## What's next

- **Courses from uploads.** Drafting concepts, prerequisites, questions and misconception tags from
  a teacher's or student's PDF with an LLM, then checking them in code (one right answer, tags that
  exist, no cycles) and with the teacher before students see them. The content pipeline
  (`backend/generation/`) is where that goes.
- **An LLM grader for explain it back**, verified against the key ideas.
- **A pilot** with a real class: comprehension of the "why" cards, and whether the gap rule finds
  the gap a teacher would name.
- **French**: the interface, the course notes, the questions, the misconception fixes and the
  coach's replies. Most Tunisian university courses are taught in French, so this comes first.
- **Tunisian Arabic (Derja)**: students ask in Derja, in Arabic script or in Latin letters
  ("ma fhemtech Bayes", "3awedli el conditional"), often mixed with French. The intent router
  needs Derja aliases for each concept, and the coach answers in the same register while keeping
  the course terms in French. The verifier's number and citation checks apply unchanged.
