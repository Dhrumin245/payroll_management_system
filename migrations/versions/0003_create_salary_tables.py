"""create salary_structures and salary_components tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-07

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "salary_structures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("basic_pay", sa.Numeric(12, 2), nullable=False),
        sa.Column("hra", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("conveyance_allowance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("basic_pay > 0", name="ck_salary_structures_basic_pay_positive"),
        sa.UniqueConstraint("employee_id", name="uq_salary_structures_employee_id"),
    )

    op.create_table(
        "salary_components",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "salary_structure_id",
            sa.Integer(),
            sa.ForeignKey("salary_structures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("component_type", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("component_type IN ('allowance', 'deduction')", name="ck_salary_components_type"),
        sa.CheckConstraint("amount >= 0", name="ck_salary_components_amount_nonnegative"),
    )


def downgrade() -> None:
    op.drop_table("salary_components")
    op.drop_table("salary_structures")
