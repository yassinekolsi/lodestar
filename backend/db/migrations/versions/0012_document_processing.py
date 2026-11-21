"""Uploads are read in the background (docs/plan/20): a document is `processing` while its pages
are read (OCR can take minutes), `review` until the student has looked at it next to the original
and validated it, `ready` once it can be searched and quizzed on, or `failed` with a reason.

Revision ID: 0012
Revises: 0011
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.documents ADD COLUMN status text NOT NULL DEFAULT 'ready'
            CHECK (status IN ('processing', 'review', 'ready', 'failed'));
        ALTER TABLE app.documents ADD COLUMN progress integer NOT NULL DEFAULT 0;
        ALTER TABLE app.documents ADD COLUMN error text;
        UPDATE app.documents SET status = 'review' WHERE review_required;
    """)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE app.documents DROP COLUMN status, DROP COLUMN progress, DROP COLUMN error"
    )
