"""create payslips table (optional PDF cache)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-07

"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payslips",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "payroll_line_item_id",
            sa.Integer(),
            sa.ForeignKey("payroll_line_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("generated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("file_path", sa.String(length=255), nullable=True),
        sa.UniqueConstraint("payroll_line_item_id", name="uq_payslips_line_item_id"),
    )


def downgrade() -> None:
    op.drop_table("payslips")
