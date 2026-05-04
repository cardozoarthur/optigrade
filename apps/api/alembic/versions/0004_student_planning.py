"""student planning and demand

Revision ID: 0004_student_planning
Revises: 0003_academic_context
Create Date: 2026-05-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_student_planning"
down_revision = "0003_academic_context"
branch_labels = None
depends_on = None

course_restriction_kind_for_create = postgresql.ENUM(
    "prerequisite", "corequisite", name="courserestrictionkind"
)
student_course_status_for_create = postgresql.ENUM(
    "completed", "failed", "enrolled", "withdrawn", name="studentcoursestatus"
)
constraint_strength_for_create = postgresql.ENUM(
    "hard", "soft", "manual_override", name="constraintstrength"
)
course_restriction_kind = postgresql.ENUM(
    "prerequisite",
    "corequisite",
    name="courserestrictionkind",
    create_type=False,
)
student_course_status = postgresql.ENUM(
    "completed",
    "failed",
    "enrolled",
    "withdrawn",
    name="studentcoursestatus",
    create_type=False,
)
constraint_strength = postgresql.ENUM(
    "hard",
    "soft",
    "manual_override",
    name="constraintstrength",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    course_restriction_kind_for_create.create(bind, checkfirst=True)
    student_course_status_for_create.create(bind, checkfirst=True)
    constraint_strength_for_create.create(bind, checkfirst=True)

    if not table_exists("students"):
        op.create_table(
            "students",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=180), nullable=False),
            sa.Column("email", sa.String(length=220), nullable=True),
            sa.Column("registration_number", sa.String(length=80), nullable=True),
            sa.Column("degree_program_id", sa.String(length=36), nullable=False),
            sa.Column("current_semester", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["degree_program_id"], ["degree_programs.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email"),
            sa.UniqueConstraint("registration_number"),
        )
    if not table_exists("course_restrictions"):
        op.create_table(
            "course_restrictions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("course_id", sa.String(length=36), nullable=False),
            sa.Column("required_course_id", sa.String(length=36), nullable=False),
            sa.Column(
                "kind",
                course_restriction_kind,
                nullable=True,
                server_default="prerequisite",
            ),
            sa.Column("strength", constraint_strength, nullable=True, server_default="hard"),
            sa.Column("minimum_grade", sa.Float(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["required_course_id"], ["courses.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    if not table_exists("student_course_history"):
        op.create_table(
            "student_course_history",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("student_id", sa.String(length=36), nullable=False),
            sa.Column("course_id", sa.String(length=36), nullable=False),
            sa.Column(
                "status",
                student_course_status,
                nullable=True,
                server_default="completed",
            ),
            sa.Column("semester", sa.String(length=32), nullable=True),
            sa.Column("grade", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    if not table_exists("student_course_requests"):
        op.create_table(
            "student_course_requests",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("student_id", sa.String(length=36), nullable=False),
            sa.Column("course_id", sa.String(length=36), nullable=False),
            sa.Column("target_semester", sa.String(length=32), nullable=False),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("source", sa.String(length=40), nullable=False, server_default="student"),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    create_index("ix_students_degree_program", "students", ["degree_program_id"])
    create_index("ix_course_restrictions_course", "course_restrictions", ["course_id"])
    create_index(
        "ix_course_restrictions_required", "course_restrictions", ["required_course_id"]
    )
    create_index("ix_student_history_student", "student_course_history", ["student_id"])
    create_index("ix_student_history_course", "student_course_history", ["course_id"])
    create_index(
        "ix_student_requests_student_semester",
        "student_course_requests",
        ["student_id", "target_semester"],
    )
    create_index(
        "ix_student_requests_course_semester",
        "student_course_requests",
        ["course_id", "target_semester"],
    )


def downgrade() -> None:
    drop_index("ix_student_requests_course_semester", "student_course_requests")
    drop_index("ix_student_requests_student_semester", "student_course_requests")
    drop_index("ix_student_history_course", "student_course_history")
    drop_index("ix_student_history_student", "student_course_history")
    drop_index("ix_course_restrictions_required", "course_restrictions")
    drop_index("ix_course_restrictions_course", "course_restrictions")
    drop_index("ix_students_degree_program", "students")
    drop_table("student_course_requests")
    drop_table("student_course_history")
    drop_table("course_restrictions")
    drop_table("students")
    bind = op.get_bind()
    student_course_status_for_create.drop(bind, checkfirst=True)
    course_restriction_kind_for_create.drop(bind, checkfirst=True)


def table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def create_index(index_name: str, table_name: str, columns: list[str]) -> None:
    if table_exists(table_name) and not index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def drop_index(index_name: str, table_name: str) -> None:
    if table_exists(table_name) and index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def drop_table(table_name: str) -> None:
    if table_exists(table_name):
        op.drop_table(table_name)
