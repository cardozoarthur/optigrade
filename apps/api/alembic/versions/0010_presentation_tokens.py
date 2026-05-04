"""presentation tokens

Revision ID: 0010_presentation_tokens
Revises: 0009_enrollment_rounds
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_presentation_tokens"
down_revision = "0009_enrollment_rounds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not table_exists("presentation_tokens"):
        op.create_table(
            "presentation_tokens",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("token", sa.String(length=96), nullable=False),
            sa.Column("kind", sa.String(length=40), nullable=False),
            sa.Column("semester", sa.String(length=32), nullable=False),
            sa.Column("degree_program_id", sa.String(length=36), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["degree_program_id"], ["degree_programs.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token"),
        )
    create_index("ix_presentation_tokens_token", "presentation_tokens", ["token"])


def downgrade() -> None:
    drop_index("ix_presentation_tokens_token", "presentation_tokens")
    if table_exists("presentation_tokens"):
        op.drop_table("presentation_tokens")


def create_index(index_name: str, table_name: str, columns: list[str]) -> None:
    if table_exists(table_name) and not index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def drop_index(index_name: str, table_name: str) -> None:
    if table_exists(table_name) and index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))
