"""enrollment rounds

Revision ID: 0009_enrollment_rounds
Revises: 0008_ufpel_pilot_metadata
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_enrollment_rounds"
down_revision = "0008_ufpel_pilot_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column(
        "student_course_requests",
        sa.Column("preference_order", sa.Integer(), nullable=True),
    )
    add_column(
        "student_course_requests",
        sa.Column("alternative_group", sa.String(length=80), nullable=True),
    )
    add_column(
        "student_course_requests",
        sa.Column("stage", sa.String(length=40), nullable=True),
    )
    if table_exists("student_course_requests"):
        op.execute("UPDATE student_course_requests SET preference_order = priority WHERE preference_order IS NULL")
        op.execute("UPDATE student_course_requests SET stage = 'pre_enrollment' WHERE stage IS NULL")
        op.alter_column("student_course_requests", "preference_order", nullable=False)
        op.alter_column("student_course_requests", "stage", nullable=False)

    if not table_exists("student_enrollments"):
        op.create_table(
            "student_enrollments",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("student_id", sa.String(length=36), nullable=False),
            sa.Column("course_id", sa.String(length=36), nullable=False),
            sa.Column("request_id", sa.String(length=36), nullable=True),
            sa.Column("run_id", sa.String(length=36), nullable=True),
            sa.Column("target_semester", sa.String(length=32), nullable=False),
            sa.Column("stage", sa.String(length=40), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("score_breakdown", sa.JSON(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["request_id"], ["student_course_requests.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["run_id"], ["optimization_runs.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    create_index(
        "ix_student_enrollments_student_semester",
        "student_enrollments",
        ["student_id", "target_semester"],
    )
    create_index(
        "ix_student_enrollments_course_semester",
        "student_enrollments",
        ["course_id", "target_semester"],
    )


def downgrade() -> None:
    drop_index("ix_student_enrollments_course_semester", "student_enrollments")
    drop_index("ix_student_enrollments_student_semester", "student_enrollments")
    if table_exists("student_enrollments"):
        op.drop_table("student_enrollments")
    drop_column("student_course_requests", "stage")
    drop_column("student_course_requests", "alternative_group")
    drop_column("student_course_requests", "preference_order")


def add_column(table_name: str, column: sa.Column) -> None:
    if table_exists(table_name) and not column_exists(table_name, column.name):
        op.add_column(table_name, column)


def drop_column(table_name: str, column_name: str) -> None:
    if table_exists(table_name) and column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)


def create_index(index_name: str, table_name: str, columns: list[str]) -> None:
    if table_exists(table_name) and not index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def drop_index(index_name: str, table_name: str) -> None:
    if table_exists(table_name) and index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))
