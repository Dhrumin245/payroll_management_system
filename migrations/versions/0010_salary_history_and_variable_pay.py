"""
0010 – Salary Revision History & Variable Pay

Adds two new tables:
  - salary_structure_history  : immutable snapshots every time a salary changes
  - variable_pay_items        : one-off per-period bonuses / deductions

No existing tables are destructively modified.
"""
from datetime import date as _date

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Modify salary_structures
    # ------------------------------------------------------------------
    op.add_column(
        "salary_structures",
        sa.Column("effective_from", sa.Date(), nullable=False, server_default="2024-01-01")
    )

    # ------------------------------------------------------------------
    # salary_structure_history
    # ------------------------------------------------------------------
    op.create_table(
        "salary_structure_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "employee_id",
            sa.Integer,
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("basic_pay", sa.Numeric(12, 2), nullable=False),
        sa.Column("hra", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column(
            "conveyance_allowance",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
        # JSON-serialised list of extra SalaryComponent rows at snapshot time
        sa.Column("components_json", sa.Text, nullable=False, server_default="[]"),
        # The date from which this salary was effective
        sa.Column(
            "effective_from",
            sa.Date,
            nullable=False,
            server_default=str(_date.today()),
        ),
        # When was this version superseded (NULL = still current snapshot)
        sa.Column("superseded_at", sa.DateTime, nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
    )
    op.create_index(
        "ix_salary_structure_history_employee_id",
        "salary_structure_history",
        ["employee_id"],
    )

    # ------------------------------------------------------------------
    # variable_pay_items
    # ------------------------------------------------------------------
    op.create_table(
        "variable_pay_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "employee_id",
            sa.Integer,
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # First-of-month date (same convention as attendance periods)
        sa.Column("period", sa.Date, nullable=False),
        sa.Column("component_type", sa.String(10), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.CheckConstraint(
            "component_type IN ('earning', 'deduction')",
            name="ck_variable_pay_items_type",
        ),
        sa.CheckConstraint("amount >= 0", name="ck_variable_pay_items_amount"),
        sa.UniqueConstraint("employee_id", "period", "name", name="uq_variable_pay_employee_period_name"),
    )
    op.create_index(
        "ix_variable_pay_items_employee_period",
        "variable_pay_items",
        ["employee_id", "period"],
    )


def downgrade() -> None:
    op.drop_table("variable_pay_items")
    op.drop_table("salary_structure_history")
    with op.batch_alter_table("salary_structures") as batch_op:
        batch_op.drop_column("effective_from")
