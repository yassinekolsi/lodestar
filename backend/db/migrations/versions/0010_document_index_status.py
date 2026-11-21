"""Persist document index status instead of claiming every saved upload is searchable."""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.documents ADD COLUMN indexed boolean NOT NULL DEFAULT false")


def downgrade() -> None:
    op.execute("ALTER TABLE app.documents DROP COLUMN indexed")
