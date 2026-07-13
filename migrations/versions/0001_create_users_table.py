"""create users table

Revision ID: 0001
Revises:
Create Date: 2026-07-06

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="admin"),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('admin', 'employee')", name="ck_users_role"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    # No FK on employee_id yet — the `employees` table doesn't exist until
    # Phase 2. Backend Schema §9 adds that constraint via a separate
    # ALTER TABLE once it does; that lands as its own migration in Phase 2,
    # not here.


def downgrade() -> None:
    op.drop_table("users")
