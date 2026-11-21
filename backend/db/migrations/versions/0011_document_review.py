"""Keep original PDFs and page transcriptions for formula review before study use."""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.documents ADD COLUMN source_pdf bytea;
        ALTER TABLE app.documents ADD COLUMN extraction jsonb NOT NULL DEFAULT '{}'::jsonb;
        ALTER TABLE app.documents ADD COLUMN review_required boolean NOT NULL DEFAULT false;
    """)


def downgrade() -> None:
    op.execute("""ALTER TABLE app.documents DROP COLUMN source_pdf,
        DROP COLUMN extraction, DROP COLUMN review_required""")
