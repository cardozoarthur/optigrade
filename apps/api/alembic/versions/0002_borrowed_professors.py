"""borrowed professors

Revision ID: 0002_borrowed_professors
Revises: 0001_initial_schema
Create Date: 2026-05-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_borrowed_professors"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not column_exists("professor_contracts", "semester"):
        op.add_column("professor_contracts", sa.Column("semester", sa.String(length=32), nullable=True))
    if not column_exists("professor_contracts", "is_borrowed"):
        op.add_column(
            "professor_contracts",
            sa.Column("is_borrowed", sa.Boolean(), server_default=sa.false(), nullable=False),
        )
    if not column_exists("professor_contracts", "borrowed_from_department"):
        op.add_column(
            "professor_contracts",
            sa.Column("borrowed_from_department", sa.String(length=120), nullable=True),
        )
    if not column_exists("professor_contracts", "loan_notes"):
        op.add_column("professor_contracts", sa.Column("loan_notes", sa.Text(), nullable=True))
    if not column_exists("optimization_runs", "semester"):
        op.add_column(
            "optimization_runs",
            sa.Column("semester", sa.String(length=32), server_default="2026/2", nullable=False),
        )


def downgrade() -> None:
    if column_exists("optimization_runs", "semester"):
        op.drop_column("optimization_runs", "semester")
    if column_exists("professor_contracts", "loan_notes"):
        op.drop_column("professor_contracts", "loan_notes")
    if column_exists("professor_contracts", "borrowed_from_department"):
        op.drop_column("professor_contracts", "borrowed_from_department")
    if column_exists("professor_contracts", "is_borrowed"):
        op.drop_column("professor_contracts", "is_borrowed")
    if column_exists("professor_contracts", "semester"):
        op.drop_column("professor_contracts", "semester")


def column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))
