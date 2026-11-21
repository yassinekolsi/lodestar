"""Student subjects and chapter labels.

Revision ID: 0009
Revises: 0008
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.subjects (
            subject_id uuid PRIMARY KEY DEFAULT uuidv7(),
            user_id uuid NOT NULL REFERENCES app.users ON DELETE CASCADE,
            name text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 100),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (user_id, subject_id)
        );
        CREATE UNIQUE INDEX subjects_name ON app.subjects (user_id, lower(name));
        ALTER TABLE app.subjects ENABLE ROW LEVEL SECURITY;
        CREATE POLICY own_rows ON app.subjects TO lodestar_app
            USING (user_id = nullif(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (user_id = nullif(current_setting('app.user_id', true), '')::uuid);
        CREATE POLICY all_rows ON app.subjects TO lodestar_jobs, lodestar_readonly USING (true);
        GRANT SELECT, INSERT, UPDATE, DELETE ON app.subjects TO lodestar_app;
        ALTER TABLE app.documents ADD COLUMN subject_id uuid;
        ALTER TABLE app.documents ADD COLUMN chapter text NOT NULL DEFAULT '';
        ALTER TABLE app.documents ADD CONSTRAINT documents_subject_owner
            FOREIGN KEY (user_id, subject_id) REFERENCES app.subjects (user_id, subject_id);
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE app.documents DROP CONSTRAINT documents_subject_owner;
        ALTER TABLE app.documents DROP COLUMN subject_id, DROP COLUMN chapter;
        DROP TABLE app.subjects;
    """)
