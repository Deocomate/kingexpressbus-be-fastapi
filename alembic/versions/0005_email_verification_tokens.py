"""Email verification tokens for signup OTP (4-digit codes).

Revision ID: 0005_email_verification_tokens
Revises: 0004_online_payment_enabled
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0005_email_verification_tokens"
down_revision = "0004_online_payment_enabled"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if "email_verification_tokens" not in tables:
        op.create_table(
            "email_verification_tokens",
            sa.Column("email", sa.String(length=255), primary_key=True),
            sa.Column("token", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )

    # Grandfather existing password accounts so login keeps working.
    op.execute(
        sa.text(
            "UPDATE users "
            "SET email_verified_at = COALESCE(email_verified_at, created_at, UTC_TIMESTAMP()) "
            "WHERE password IS NOT NULL AND email_verified_at IS NULL"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    if "email_verification_tokens" in tables:
        op.drop_table("email_verification_tokens")
