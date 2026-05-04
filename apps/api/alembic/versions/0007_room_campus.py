"""room campus compatibility

Revision ID: 0007_room_campus
Revises: 0006_degree_program_schedule
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_room_campus"
down_revision = "0006_degree_program_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column("rooms", sa.Column("campus_id", sa.String(length=36), nullable=True))
    create_fk(
        "fk_rooms_campus_id_campuses",
        "rooms",
        "campuses",
        ["campus_id"],
        ["id"],
        ondelete="SET NULL",
    )
    create_index("ix_rooms_campus", "rooms", ["campus_id"])


def downgrade() -> None:
    drop_index("ix_rooms_campus", "rooms")
    drop_fk("fk_rooms_campus_id_campuses", "rooms")
    drop_column("rooms", "campus_id")


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


def create_fk(
    constraint_name: str,
    source_table: str,
    referent_table: str,
    local_cols: list[str],
    remote_cols: list[str],
    *,
    ondelete: str | None = None,
) -> None:
    if (
        table_exists(source_table)
        and table_exists(referent_table)
        and not foreign_key_exists(source_table, constraint_name)
    ):
        op.create_foreign_key(
            constraint_name,
            source_table,
            referent_table,
            local_cols,
            remote_cols,
            ondelete=ondelete,
        )


def drop_fk(constraint_name: str, table_name: str) -> None:
    if table_exists(table_name) and foreign_key_exists(table_name, constraint_name):
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")


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


def foreign_key_exists(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return any(
        foreign_key.get("name") == constraint_name
        for foreign_key in inspector.get_foreign_keys(table_name)
    )
