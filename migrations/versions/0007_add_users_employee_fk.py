"""add foreign key from users.employee_id to employees.id

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-07

This is the deferred step flagged in migration 0001 and in Backend Schema
§9's DDL: `employees` didn't exist when `users` was created, so this
constraint gets added now that it does.
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite can't ADD CONSTRAINT directly — batch mode recreates the table
    # under the hood to simulate it. On Postgres this just runs as a normal
    # ALTER TABLE.
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_foreign_key("fk_users_employee", "employees", ["employee_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_employee", type_="foreignkey")
