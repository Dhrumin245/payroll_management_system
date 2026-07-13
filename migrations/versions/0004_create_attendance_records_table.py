"""create attendance_records table

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-07

"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("days_present", sa.Numeric(4, 1), nullable=False),
        sa.Column("days_on_leave", sa.Numeric(4, 1), nullable=False, server_default="0"),
        sa.Column("total_working_days", sa.Numeric(4, 1), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("employee_id", "period", name="uq_attendance_employee_period"),
        sa.CheckConstraint("days_present >= 0", name="ck_attendance_days_present_nonnegative"),
        sa.CheckConstraint("days_on_leave >= 0", name="ck_attendance_days_on_leave_nonnegative"),
        sa.CheckConstraint(
            "days_present + days_on_leave <= total_working_days", name="ck_attendance_days_within_working_days"
        ),
    )
    op.create_index("idx_attendance_period", "attendance_records", ["period"])


def downgrade() -> None:
    op.drop_index("idx_attendance_period", table_name="attendance_records")
    op.drop_table("attendance_records")
