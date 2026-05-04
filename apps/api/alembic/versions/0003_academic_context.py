"""academic context for courses

Revision ID: 0003_academic_context
Revises: 0002_borrowed_professors
Create Date: 2026-05-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_academic_context"
down_revision = "0002_borrowed_professors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not table_exists("campuses"):
        op.create_table(
            "campuses",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("city", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if not table_exists("degree_programs"):
        op.create_table(
            "degree_programs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("campus_id", sa.String(length=36), nullable=True),
            sa.Column("name", sa.String(length=180), nullable=False),
            sa.Column("code", sa.String(length=40), nullable=True),
            sa.Column("department", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    add_course_column("code", sa.Column("code", sa.String(length=40), nullable=True))
    add_course_column("campus_id", sa.Column("campus_id", sa.String(length=36), nullable=True))
    add_course_column(
        "degree_program_id", sa.Column("degree_program_id", sa.String(length=36), nullable=True)
    )
    if not column_exists("courses", "theoretical_hours"):
        op.add_column("courses", sa.Column("theoretical_hours", sa.Integer(), nullable=True))
        op.execute("UPDATE courses SET theoretical_hours = workload_hours WHERE theoretical_hours IS NULL")
        op.alter_column("courses", "theoretical_hours", nullable=False)
    add_course_column(
        "practical_hours",
        sa.Column("practical_hours", sa.Integer(), server_default="0", nullable=False),
    )
    add_course_column("context_key", sa.Column("context_key", sa.String(length=160), nullable=True))
    add_course_column(
        "shareable", sa.Column("shareable", sa.Boolean(), server_default=sa.true(), nullable=False)
    )

    create_fk("fk_courses_campus_id_campuses", "courses", "campuses", ["campus_id"], ["id"])
    create_fk(
        "fk_courses_degree_program_id_degree_programs",
        "courses",
        "degree_programs",
        ["degree_program_id"],
        ["id"],
    )
    create_index("ix_degree_programs_campus", "degree_programs", ["campus_id"])
    create_index("ix_courses_campus", "courses", ["campus_id"])
    create_index("ix_courses_degree_program", "courses", ["degree_program_id"])
    create_index("ix_courses_context_key", "courses", ["context_key"])


def downgrade() -> None:
    drop_index("ix_courses_context_key", "courses")
    drop_index("ix_courses_degree_program", "courses")
    drop_index("ix_courses_campus", "courses")
    drop_index("ix_degree_programs_campus", "degree_programs")
    drop_fk("fk_courses_degree_program_id_degree_programs", "courses")
    drop_fk("fk_courses_campus_id_campuses", "courses")

    for column_name in [
        "shareable",
        "context_key",
        "practical_hours",
        "theoretical_hours",
        "degree_program_id",
        "campus_id",
        "code",
    ]:
        if column_exists("courses", column_name):
            op.drop_column("courses", column_name)

    if table_exists("degree_programs"):
        op.drop_table("degree_programs")
    if table_exists("campuses"):
        op.drop_table("campuses")


def add_course_column(column_name: str, column: sa.Column) -> None:
    if not column_exists("courses", column_name):
        op.add_column("courses", column)


def table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def create_index(index_name: str, table_name: str, columns: list[str]) -> None:
    if table_exists(table_name) and not index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def drop_index(index_name: str, table_name: str) -> None:
    if table_exists(table_name) and index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def create_fk(
    constraint_name: str,
    source_table: str,
    referent_table: str,
    local_cols: list[str],
    remote_cols: list[str],
) -> None:
    if table_exists(source_table) and not fk_exists(
        source_table, constraint_name, local_cols, referent_table, remote_cols
    ):
        op.create_foreign_key(
            constraint_name, source_table, referent_table, local_cols, remote_cols, ondelete="SET NULL"
        )


def drop_fk(constraint_name: str, table_name: str) -> None:
    if table_exists(table_name) and fk_exists(table_name, constraint_name):
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")


def fk_exists(
    table_name: str,
    constraint_name: str,
    local_cols: list[str] | None = None,
    referent_table: str | None = None,
    remote_cols: list[str] | None = None,
) -> bool:
    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys(table_name):
        if foreign_key["name"] == constraint_name:
            return True
        if (
            local_cols
            and referent_table
            and remote_cols
            and foreign_key.get("constrained_columns") == local_cols
            and foreign_key.get("referred_table") == referent_table
            and foreign_key.get("referred_columns") == remote_cols
        ):
            return True
    return False
