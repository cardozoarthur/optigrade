"""complex student preferences

Revision ID: 0011_complex_student_preferences
Revises: 0010_presentation_tokens
Create Date: 2026-05-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_complex_student_preferences"
down_revision = "0010_presentation_tokens"
branch_labels = None
depends_on = None

constraint_strength = postgresql.ENUM(
    "hard",
    "soft",
    "manual_override",
    name="constraintstrength",
    create_type=False,
)


def upgrade() -> None:
    add_column_if_missing("student_course_requests", sa.Column("desired_day", sa.Integer(), nullable=True))
    add_column_if_missing(
        "student_course_requests",
        sa.Column("desired_start_minute", sa.Integer(), nullable=True),
    )
    add_column_if_missing(
        "student_course_requests",
        sa.Column("desired_end_minute", sa.Integer(), nullable=True),
    )
    add_column_if_missing(
        "student_course_requests",
        sa.Column(
            "time_preference_strength",
            constraint_strength,
            server_default="soft",
            nullable=False,
        ),
    )


def downgrade() -> None:
    drop_column_if_exists("student_course_requests", "time_preference_strength")
    drop_column_if_exists("student_course_requests", "desired_end_minute")
    drop_column_if_exists("student_course_requests", "desired_start_minute")
    drop_column_if_exists("student_course_requests", "desired_day")


def add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if table_exists(table_name) and not column_exists(table_name, column.name):
        op.add_column(table_name, column)


def drop_column_if_exists(table_name: str, column_name: str) -> None:
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
