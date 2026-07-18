"""
0011 – Statutory Configuration (PF, ESI, PT)

Adds two new tables:
  - statutory_configs  : company-wide key-value settings (PF/ESI toggles, PT state)
  - pt_slabs           : Professional Tax slab lookup table (state-specific)

Seeds default Maharashtra (MH) PT slabs and sets PF/ESI to disabled by default.
"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # statutory_configs (key-value settings)
    # ------------------------------------------------------------------
    op.create_table(
        "statutory_configs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(60), unique=True, nullable=False),
        sa.Column("value", sa.String(255), nullable=False, server_default=""),
        sa.Column(
            "updated_by_user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
    )

    # Seed default configs
    op.execute(
        "INSERT INTO statutory_configs (key, value) VALUES ('pf_enabled', 'false')"
    )
    op.execute(
        "INSERT INTO statutory_configs (key, value) VALUES ('esi_enabled', 'false')"
    )
    op.execute(
        "INSERT INTO statutory_configs (key, value) VALUES ('pt_enabled', 'false')"
    )
    op.execute(
        "INSERT INTO statutory_configs (key, value) VALUES ('pt_state', 'MH')"
    )

    # ------------------------------------------------------------------
    # pt_slabs (Professional Tax slab table)
    # ------------------------------------------------------------------
    op.create_table(
        "pt_slabs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("state_code", sa.String(10), nullable=False),
        sa.Column("gross_from", sa.Numeric(12, 2), nullable=False),
        sa.Column("gross_to", sa.Numeric(12, 2), nullable=True),  # NULL = infinity
        sa.Column("monthly_tax", sa.Numeric(8, 2), nullable=False),
    )
    op.create_index("ix_pt_slabs_state_code", "pt_slabs", ["state_code"])

    # Seed Maharashtra (MH) PT slabs (2024 rates)
    op.execute(
        "INSERT INTO pt_slabs (state_code, gross_from, gross_to, monthly_tax) "
        "VALUES ('MH', 0, 7500, 0)"
    )
    op.execute(
        "INSERT INTO pt_slabs (state_code, gross_from, gross_to, monthly_tax) "
        "VALUES ('MH', 7501, 10000, 175)"
    )
    op.execute(
        "INSERT INTO pt_slabs (state_code, gross_from, gross_to, monthly_tax) "
        "VALUES ('MH', 10001, NULL, 200)"
    )

    # Karnataka (KA) slabs
    op.execute(
        "INSERT INTO pt_slabs (state_code, gross_from, gross_to, monthly_tax) "
        "VALUES ('KA', 0, 15000, 0)"
    )
    op.execute(
        "INSERT INTO pt_slabs (state_code, gross_from, gross_to, monthly_tax) "
        "VALUES ('KA', 15001, NULL, 200)"
    )


def downgrade() -> None:
    op.drop_table("pt_slabs")
    op.drop_table("statutory_configs")
