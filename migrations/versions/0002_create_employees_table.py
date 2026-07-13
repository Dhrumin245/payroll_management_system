"""create employees and employee_bank_details tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-07

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_code", sa.String(length=20), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("designation", sa.String(length=80), nullable=False),
        sa.Column("joining_date", sa.Date(), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="active"),
        sa.Column("deactivated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_employees_status"),
        sa.UniqueConstraint("employee_code", name="uq_employees_employee_code"),
    )
    op.create_index("idx_employees_status", "employees", ["status"])

    op.create_table(
        "employee_bank_details",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("account_holder_name", sa.String(length=120), nullable=False),
        sa.Column("account_number_encrypted", sa.Text(), nullable=False),
        sa.Column("account_number_last4", sa.String(length=4), nullable=False),
        sa.Column("ifsc_code", sa.String(length=20), nullable=True),
        sa.Column("bank_name", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("employee_id", name="uq_employee_bank_details_employee_id"),
    )


def downgrade() -> None:
    op.drop_table("employee_bank_details")
    op.drop_index("idx_employees_status", table_name="employees")
    op.drop_table("employees")
