"""add manager role to users.role check constraint

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-14

Extends the role CHECK constraint from ('admin', 'employee') to
('admin', 'manager', 'employee'), enabling the RBAC tier introduced
in Phase 8.  SQLite can't ALTER a CHECK constraint in place, so
batch_alter_table recreates the table transparently.  On Postgres this
becomes a normal ALTER TABLE … DROP CONSTRAINT / ADD CONSTRAINT pair.
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_users_role", type_="check")
        batch_op.create_check_constraint(
            "ck_users_role",
            "role IN ('admin', 'manager', 'employee')",
        )


def downgrade() -> None:
    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_users_role", type_="check")
        batch_op.create_check_constraint(
            "ck_users_role",
            "role IN ('admin', 'employee')",
        )
