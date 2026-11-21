"""A student's own course documents (docs/plan/20): the files they upload and their passages, each
with its page, so every answer drawn from them can cite where it came from. The passages are also
indexed in Qdrant (`documents` collection) for search; Postgres stays the source of truth.

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
CREATE TABLE app.documents (
    doc_id      uuid PRIMARY KEY DEFAULT uuidv7(),
    user_id     uuid NOT NULL REFERENCES app.users ON DELETE CASCADE,
    title       text NOT NULL,
    filename    text NOT NULL,
    pages       integer NOT NULL,
    passages    integer NOT NULL,
    concepts    jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX documents_user ON app.documents (user_id, created_at DESC);

CREATE TABLE app.document_passages (
    passage_id  uuid PRIMARY KEY DEFAULT uuidv7(),
    doc_id      uuid NOT NULL REFERENCES app.documents ON DELETE CASCADE,
    user_id     uuid NOT NULL REFERENCES app.users ON DELETE CASCADE,
    page        integer NOT NULL,
    position    integer NOT NULL,
    text        text NOT NULL,
    concepts    text[] NOT NULL DEFAULT '{}'
);
CREATE INDEX document_passages_doc ON app.document_passages (doc_id, position);
CREATE INDEX document_passages_user ON app.document_passages (user_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON app.documents, app.document_passages TO lodestar_app;
"""

POLICIES = """
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['documents', 'document_passages'] LOOP
        EXECUTE format('ALTER TABLE app.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY own_rows ON app.%I TO lodestar_app'
            ' USING (user_id = nullif(current_setting(''app.user_id'', true), '''')::uuid)'
            ' WITH CHECK (user_id = nullif(current_setting(''app.user_id'', true), '''')::uuid)',
            t);
        EXECUTE format(
            'CREATE POLICY all_rows ON app.%I TO lodestar_jobs, lodestar_readonly USING (true)', t);
    END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute(UPGRADE)
    op.execute(POLICIES)


def downgrade() -> None:
    op.execute("DROP TABLE app.document_passages; DROP TABLE app.documents;")
