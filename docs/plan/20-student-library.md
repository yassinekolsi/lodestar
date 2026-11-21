# Student subjects and chapter library

Students can create subjects and upload PDF, Markdown or text chapters from Documents. Each file
keeps its owner, subject, chapter label, page count and original PDF in Postgres. Passages retain
page citations; Qdrant stores searchable copies using the existing user-scoped memory helper.
Alembic migrations 0009–0011 define subjects, index status and transcription review. Library
changes append `library.changed` events. Account export includes original PDFs as base64; account
deletion removes subjects, passages, documents and their search entries.

Native text PDFs use pypdf. Scanned pages use Gemini 3.5 Flash Lite through the LLM factory, with
the student's encrypted Gemini credential and explicit Cloud AI consent. An independent second
request checks the transcription against the original page. No local OCR fallback is used.
Errors and rate limits leave the source unapproved; provider errors never include credentials.

Every OCR upload requires review, even when Gemini reports no uncertainty. Students compare the
original PDF with extracted page text and formula previews, edit it, then explicitly approve it.
Unresolved `[unclear]` markers and malformed formula boundaries block approval. Unapproved files
are excluded from quizzes, explanations and search results. Approval replaces page passages,
refreshes concept tags and indexes the reviewed text. Search availability is shown separately
from whether a chapter can supply a quiz from Postgres.

The selected document ID follows Check understanding and Explain this chapter through the agent;
ownership is checked again on the backend. Generated quiz questions must cite verbatim evidence
on an existing source page. This verifies source grounding, not the correctness of the source or
every generated answer. Uploaded chapters do not automatically become a validated prerequisite
map. The curated probability course remains the source of concept mastery and gap decisions.

Validation: `tests/backend/agent/test_documents.py`, `frontend/e2e/documents.spec.ts` and the key
isolation and account-data tests. The seven supplied local PDFs are demo inputs, not repository
assets. `python -m backend.documents.import_demo /src` imports them inside the development app.

## Review findings

The 29 probability scan pages received Gemini transcription and a second visual pass. Comparing
selected original pages manually still found wrong handwritten denominators, a table cell and
table headings. Corrections were applied to the local demo; chapter 3 pages 10 and 12 retain
uncertainty flags. All probability scans remain behind review. There is no measured OCR accuracy
claim, and a successful formula rendering check does not establish mathematical correctness.

Use `python -m backend.documents.audit /src /src/.artifacts/ocr-review` to export private review
notes and page images (the image export needs Poppler). These artifacts remain ignored.
