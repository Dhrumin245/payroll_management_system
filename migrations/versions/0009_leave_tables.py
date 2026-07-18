"""create leave management tables

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-14

Creates the tables required for leave type configurations, leave applications,
and leave balances.
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. create leave_types table
    op.create_table(
        "leave_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=60), nullable=False, unique=True),
        sa.Column("max_days_per_year", sa.Numeric(precision=5, scale=1), nullable=True),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    # 2. create leave_requests table
    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("leave_type_id", sa.Integer(), sa.ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=15), nullable=False, server_default="pending"),
        sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_leave_requests_status"),
        sa.CheckConstraint("start_date <= end_date", name="ck_leave_requests_dates"),
    )

    # 3. create leave_balances table
    op.create_table(
        "leave_balances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("leave_type_id", sa.Integer(), sa.ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("days_used", sa.Numeric(precision=5, scale=1), nullable=False, server_default="0.0"),
        sa.UniqueConstraint("employee_id", "leave_type_id", "year", name="uq_leave_balance_employee_type_year"),
    )


def downgrade() -> None:
    op.drop_table("leave_balances")
    op.drop_table("leave_requests")
    op.drop_table("leave_types")
