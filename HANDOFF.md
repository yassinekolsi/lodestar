# Handoff: Lodestar study coach (state as of 2026-11-21)

## The challenge

> Comment concevoir une solution fondée sur l'intelligence artificielle capable de répondre aux
> difficultés de compréhension des étudiants, d'enrichir leurs processus d'apprentissage et
> d'améliorer durablement leur expérience éducative.

Lodestar is an AI study coach. It started as a fork of a cognitive-training app, and the scoring
engine, the LangGraph agent, the verified coach, memory and ethics were kept. The repo and the UI
are in English.

## Rules

- Repo: `E:\web-tp\the-upside-hack`, branch `main`.
- **Commit as you go. Every commit message is fully lowercase, first letter included**, in the form
  `area: what changed`.
- Every text file is LF (`.gitattributes`). LightGBM model files with CRLF crash the backend at
  startup.
- Don't patch source with python heredocs that contain `\b` or `\n` in the replacement text: they
  get written as control characters. Use the editor or a script file.
- `.env` is gitignored and must stay out of git.

## Running it (Docker; there's no local Python 3.14)

- Postgres and Qdrant: `docker compose up -d postgres qdrant` (compose project `lodestar-upside`).
- Backend: container `upside-api` (image `lodestar-dev`, which is the backend image plus dev
  dependencies), repo mounted at `/src`, `uvicorn --reload` on :8000.
- Frontend: container `upside-web` (image `lodestar-frontend`), `frontend/src` mounted,
  `npx vite --host 0.0.0.0` on :5173 with `CHOKIDAR_USEPOLLING=true`.
- Migrate: `alembic upgrade head` (0008 adds the document tables).
- Reseed: `python -m backend.db.seed --reset --token`, then `python -m backend.db.seed_memory` inside
  `upside-api`. The seed prints the sign-in link.
- Tests: run per file, for example `python -m pytest -q tests/backend/agent/test_learning.py`. The
  full suite takes more than 25 minutes.
- Lint: `ruff check backend`, `mypy`; in the frontend, `npx tsc --noEmit`, `npx eslint src`.

## What's done

- **Course model.** `registry/courses/probability.yaml`: Probability 1, 12 concepts with
  prerequisites, 67 questions, 104 wrong options tagged with 36 misconceptions, each with a fix.
  `backend/registry/course.py` validates it. Each concept becomes a dimension with two exercises,
  `quiz_<concept>` and `explain_<concept>`.
- **Scoring.** Mastery is the chance of getting a typical question right, with an 80% range
  (`backend/scoring/norms.py`). Rushed rounds are detected per exercise (a quiz is rushed under
  2.5 s per answer). An answer found with hints counts 0.75 or 0.5.
- **Planner** (`backend/agent/nodes/play.py`, `backend/agent/learning.py`):
  - Prerequisite-gap rule: a struggling concept (under 45%, with the top of its range under 50%)
    sends the student to its deepest shaky prerequisite first.
  - Plateau: switch to explain-it-back.
  - Consolidate: explain-it-back after a strong quiz.
  - Spaced review.
- **Coach tools** (`backend/agent/study_tools.py`):
  - `teach`: the student's own uploaded pages first, then the course notes, their mastery, their
    usual mix-up and any gap.
  - `mistakes`: the misconceptions behind their wrong answers.
  - Intents (`backend/agent/intents.py`) use the concept aliases. "Quiz me on my notes" routes to
    `quiz_notes`.
- **API:**
  - `/course`: the concept map.
  - `/class`: the teacher view, counts only, no names.
  - `/registry`: hides the questions and answers.
  - `/documents`: POST, GET, DELETE, and `/documents/search`.
- **Documents and RAG** (backend only for now):
  - `backend/documents/ingest.py`: pypdf extraction, then passages that keep their page number,
    tagged with the concepts they mention.
  - `backend/documents/library.py`: Postgres tables `app.documents` and `app.document_passages`
    (migration 0008, row-level security), plus the Qdrant collection `documents` (hybrid dense +
    BM25 search, per user).
  - `backend/documents/questions.py`: quiz questions from the student's notes. Without a model,
    code builds them from definitions and term gaps; with a model, it drafts them and code checks
    each one.
  - Demo PDFs: `docs/demo/probability-lecture-4.pdf` and `docs/demo/data-structures-stacks-queues.pdf`.
- **Frontend:**
  - Quiz and explain plugins (`frontend/src/games/{quiz,explain}`), with "How sure?" on every
    answer, hints, and the misconception plus its fix in the feedback.
  - `ConceptMap.tsx` (prerequisite lines, mastery with ranges, the gap path), `ClassPanel.tsx`.
  - Lesson and mistakes cards, a concept page, and the study copy.
- **Seed:** Alex, five weeks into the course, plus 24 classmates, generated through the real
  scorer. Alex shows a plateau on conditional probability, a gap from Bayes to conditional
  probability, and a recurring inverse-conditional mix-up.
- **Evaluation:**
  - `make sim N=200`: recovery r 0.84 after 10 sessions, 80% ranges hold 83%, success rate 80%,
    placement σ 0.86, rushed and cheating rounds caught with precision and recall 1.00.
  - `python -m simulator.gap_eval --users 200`: finds a planted gap 72% of the time, against 24%
    for "practise your weakest concept", with a 5% false-alarm rate.
- **Docs:** `README.md`, `docs/EVIDENCE.md`, `docs/plan/19-study-coach.md`, `docs/screens/`.

## Next steps, in priority order

1. **Fix chunking** in `backend/documents/ingest.py`. `clean()` merges lines too aggressively, so a
   two-page PDF gives only 4 or 5 passages, and the title picks up the author line. Split on headings
   and short paragraphs, aim for about 400–700 characters per passage, and clean up `title_of`.
   Re-upload the demo PDFs and check `/documents/search`.
2. **Frontend Documents panel:**
   - New nav item: upload (drag and drop), list with pages and the concepts found, delete, and a
     search box.
   - Render the `sources` card (`card: 'sources'`, plus `sources` on the `lesson` card) with
     title, page and passage. Add both to `AgentCard` in `frontend/src/api/types.ts` and to
     `app/StressCases.tsx`.
   - Home: an "Upload your course" action and a chip "Quiz me on my notes".
   - Regenerate the API types: `python -m backend.contracts.export`, then `npx openapi-typescript`.
3. **Test `quiz_notes` end to end** in the browser. The quiz plugin needs `content.section`. Check
   the questions code builds from the Data Structures PDF; that document matches no course concept,
   so the quiz is unscored practice.
4. **Concept map: link uploads.** Show "in your slides: p. X" per concept, using `documents.concepts`.
5. **Optional, needs an LLM key:** draft a whole course (concepts, prerequisites, questions) from an
   upload, shown to the student as a draft.
6. **Tests:**
   - About 90 old tests fail because they reference removed cognitive games. Rewrite or delete
     them; start with `test_rounds.py`, `test_mcp_cli.py`, `test_converse.py`, `test_twin_store.py`,
     `test_registry.py`, `test_policy.py`, `test_stress_cases.py`.
   - Add tests for ingest, search and `quiz_notes`.
7. **Docs:** add `docs/plan/20-documents.md`, update the README and `docs/EVIDENCE.md` with upload,
   RAG and quizzes from notes, and take new screenshots.
8. **French and Tunisian Arabic (Derja): done (2026-11-21).** Interface in three languages
   (`frontend/src/i18n`, picker in the sidebar and Settings, `?lang=fr|tn`), the course in French
   (`registry/courses/i18n/`), French and Derja routing, the coach told the language, fixed replies
   in all three (`backend/i18n.py`). Left: a read-through by Tunisian students; the panels off the
   demo path (Insights, Agent, Experiments, Memory, About, Documents, parts of Settings) are still
   English. Deploying: `render.yaml`, root `Dockerfile`, [docs/DEPLOY.md](docs/DEPLOY.md).
9. **Pitch and demo script** for the challenge. The old brain-training demo script
   (`docs/demo-script.md`) and report (`docs/report/`) were deleted; write new ones from scratch:
   - Upload a PDF.
   - Ask a question and get an answer that cites a page.
   - Take a quiz from the upload.
   - Show the gap rule, the misconception feedback, the concept map and the class view.
