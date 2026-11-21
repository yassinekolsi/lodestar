"""Let the connecting user switch to the row-level-security role on managed Postgres (Neon).

Every request runs `SET LOCAL ROLE lodestar_app` (backend/db/twin_store.py, user_scope), so the
rest of its transaction sees only one student's rows (migration 0007). Locally the app connects as
a superuser, which may switch to any role. On Neon it connects as the database owner, which
created lodestar_app in migration 0001 but, since Postgres 16, isn't a member of it: creating a
role grants the ADMIN option, not the right to SET it. Without this, every signed-in request fails
with "permission denied to set role".

The grant is only made for a user that isn't a superuser, and with INHERIT FALSE: the owner gains
the switch, not lodestar_app's privileges by default.

Revision ID: 0013
Revises: 0012
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
DO $$
BEGIN
    IF NOT (SELECT rolsuper FROM pg_roles WHERE rolname = current_user) THEN
        EXECUTE format('GRANT lodestar_app TO %I WITH SET TRUE, INHERIT FALSE', current_user);
    END IF;
END $$;
""")


def downgrade() -> None:
    op.execute("""
DO $$
BEGIN
    IF NOT (SELECT rolsuper FROM pg_roles WHERE rolname = current_user) THEN
        EXECUTE format('REVOKE lodestar_app FROM %I', current_user);
    END IF;
END $$;
""")
