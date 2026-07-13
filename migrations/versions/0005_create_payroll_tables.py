"""create payroll_runs, payroll_line_items, and payroll_line_item_components tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-07

"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payroll_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("run_date", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("status", sa.String(length=15), nullable=False, server_default="completed"),
        sa.Column("total_gross", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_deductions", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_net_pay", sa.Numeric(14, 2), nullable=False),
        sa.Column("employee_count", sa.Integer(), nullable=False),
        sa.Column("run_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('completed', 'failed')", name="ck_payroll_runs_status"),
        sa.UniqueConstraint("period", name="uq_payroll_runs_period"),
    )

    op.create_table(
        "payroll_line_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "payroll_run_id", sa.Integer(), sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("employee_code_snapshot", sa.String(length=20), nullable=False),
        sa.Column("employee_name_snapshot", sa.String(length=120), nullable=False),
        sa.Column("days_present_snapshot", sa.Numeric(4, 1), nullable=False),
        sa.Column("days_on_leave_snapshot", sa.Numeric(4, 1), nullable=False),
        sa.Column("gross_pay", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_deductions", sa.Numeric(12, 2), nullable=False),
        sa.Column("net_pay", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("payroll_run_id", "employee_id", name="uq_payroll_line_items_run_employee"),
    )
    op.create_index("idx_payroll_line_items_employee", "payroll_line_items", ["employee_id"])
    op.create_index("idx_payroll_line_items_run", "payroll_line_items", ["payroll_run_id"])

    op.create_table(
        "payroll_line_item_components",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "payroll_line_item_id",
            sa.Integer(),
            sa.ForeignKey("payroll_line_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("component_type", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint(
            "component_type IN ('earning', 'deduction')", name="ck_payroll_line_item_components_type"
        ),
    )


def downgrade() -> None:
    op.drop_table("payroll_line_item_components")
    op.drop_index("idx_payroll_line_items_run", table_name="payroll_line_items")
    op.drop_index("idx_payroll_line_items_employee", table_name="payroll_line_items")
    op.drop_table("payroll_line_items")
    op.drop_table("payroll_runs")
