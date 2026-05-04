"""degree program regular schedule window

Revision ID: 0006_degree_program_schedule
Revises: 0005_better_auth
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_degree_program_schedule"
down_revision = "0005_better_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column("degree_programs", sa.Column("schedule_start_minute", sa.Integer(), nullable=True))
    add_column("degree_programs", sa.Column("schedule_end_minute", sa.Integer(), nullable=True))


def downgrade() -> None:
    drop_column("degree_programs", "schedule_end_minute")
    drop_column("degree_programs", "schedule_start_minute")


def add_column(table_name: str, column: sa.Column) -> None:
    if table_exists(table_name) and not column_exists(table_name, column.name):
        op.add_column(table_name, column)


def drop_column(table_name: str, column_name: str) -> None:
    if table_exists(table_name) and column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)


def table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))
