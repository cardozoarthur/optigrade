"""better auth organization tables

Revision ID: 0005_better_auth
Revises: 0004_student_planning
Create Date: 2026-05-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_better_auth"
down_revision = "0004_student_planning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_user",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("emailVerified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("image", sa.Text(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("profileType", sa.Text(), nullable=True),
        sa.Column("professorId", sa.Text(), nullable=True),
        sa.Column("studentId", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="auth_user_email_key"),
    )
    op.create_table(
        "auth_session",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("expiresAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("ipAddress", sa.Text(), nullable=True),
        sa.Column("userAgent", sa.Text(), nullable=True),
        sa.Column("userId", sa.Text(), nullable=False),
        sa.Column("activeOrganizationId", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["userId"], ["auth_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="auth_session_token_key"),
    )
    op.create_table(
        "auth_account",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("accountId", sa.Text(), nullable=False),
        sa.Column("providerId", sa.Text(), nullable=False),
        sa.Column("userId", sa.Text(), nullable=False),
        sa.Column("accessToken", sa.Text(), nullable=True),
        sa.Column("refreshToken", sa.Text(), nullable=True),
        sa.Column("idToken", sa.Text(), nullable=True),
        sa.Column("accessTokenExpiresAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refreshTokenExpiresAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("password", sa.Text(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["userId"], ["auth_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "auth_verification",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("identifier", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("expiresAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "auth_organization",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("logo", sa.Text(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="auth_organization_slug_key"),
    )
    op.create_table(
        "auth_member",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organizationId", sa.Text(), nullable=False),
        sa.Column("userId", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="member"),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organizationId"], ["auth_organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["userId"], ["auth_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "auth_invitation",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organizationId", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("expiresAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("inviterId", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["organizationId"], ["auth_organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inviterId"], ["auth_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("auth_session_userId_idx", "auth_session", ["userId"])
    op.create_index("auth_account_userId_idx", "auth_account", ["userId"])
    op.create_index("auth_verification_identifier_idx", "auth_verification", ["identifier"])
    op.create_index("auth_organization_slug_idx", "auth_organization", ["slug"])
    op.create_index("auth_member_organizationId_idx", "auth_member", ["organizationId"])
    op.create_index("auth_member_userId_idx", "auth_member", ["userId"])
    op.create_index("auth_invitation_organizationId_idx", "auth_invitation", ["organizationId"])
    op.create_index("auth_invitation_email_idx", "auth_invitation", ["email"])


def downgrade() -> None:
    op.drop_index("auth_invitation_email_idx", table_name="auth_invitation")
    op.drop_index("auth_invitation_organizationId_idx", table_name="auth_invitation")
    op.drop_index("auth_member_userId_idx", table_name="auth_member")
    op.drop_index("auth_member_organizationId_idx", table_name="auth_member")
    op.drop_index("auth_organization_slug_idx", table_name="auth_organization")
    op.drop_index("auth_verification_identifier_idx", table_name="auth_verification")
    op.drop_index("auth_account_userId_idx", table_name="auth_account")
    op.drop_index("auth_session_userId_idx", table_name="auth_session")
    op.drop_table("auth_invitation")
    op.drop_table("auth_member")
    op.drop_table("auth_organization")
    op.drop_table("auth_verification")
    op.drop_table("auth_account")
    op.drop_table("auth_session")
    op.drop_table("auth_user")
