"""Allow null passwords on users (guest checkout accounts).

Revision ID: 0003_users_password_nullable
Revises: 0002_mail_jobs
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_users_password_nullable"
down_revision = "0002_mail_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "password",
        existing_type=sa.String(length=255),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "password",
        existing_type=sa.String(length=255),
        nullable=False,
    )
