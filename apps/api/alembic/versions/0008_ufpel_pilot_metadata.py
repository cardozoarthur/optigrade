"""ufpel pilot metadata

Revision ID: 0008_ufpel_pilot_metadata
Revises: 0007_room_campus
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_ufpel_pilot_metadata"
down_revision = "0007_room_campus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column("degree_programs", sa.Column("required_hours", sa.Integer(), nullable=True))
    add_column("degree_programs", sa.Column("minimum_semesters", sa.Integer(), nullable=True))
    add_column("degree_programs", sa.Column("maximum_semesters", sa.Integer(), nullable=True))
    add_column("degree_programs", sa.Column("legal_notes", sa.Text(), nullable=True))
    add_column("degree_programs", sa.Column("source_url", sa.String(length=320), nullable=True))
    add_column("courses", sa.Column("approval_grade", sa.Float(), nullable=True))
    add_column("courses", sa.Column("approval_frequency_percent", sa.Integer(), nullable=True))
    add_column("courses", sa.Column("source_url", sa.String(length=320), nullable=True))
    add_column("courses", sa.Column("official_period", sa.String(length=32), nullable=True))
    add_column("courses", sa.Column("official_class", sa.String(length=40), nullable=True))
    add_column("courses", sa.Column("official_schedule", sa.JSON(), nullable=True))
    if table_exists("courses") and column_exists("courses", "official_schedule"):
        op.execute("UPDATE courses SET official_schedule = '[]' WHERE official_schedule IS NULL")
        op.alter_column("courses", "official_schedule", nullable=False)


def downgrade() -> None:
    drop_column("courses", "official_schedule")
    drop_column("courses", "official_class")
    drop_column("courses", "official_period")
    drop_column("courses", "source_url")
    drop_column("courses", "approval_frequency_percent")
    drop_column("courses", "approval_grade")
    drop_column("degree_programs", "source_url")
    drop_column("degree_programs", "legal_notes")
    drop_column("degree_programs", "maximum_semesters")
    drop_column("degree_programs", "minimum_semesters")
    drop_column("degree_programs", "required_hours")


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
