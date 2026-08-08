"""Add online_payment_enabled to web_profiles.

Revision ID: 0004_online_payment_enabled
Revises: 0003_users_password_nullable
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0004_online_payment_enabled"
down_revision = "0003_users_password_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {col["name"] for col in inspect(bind).get_columns("web_profiles")}
    if "online_payment_enabled" in columns:
        return
    op.add_column(
        "web_profiles",
        sa.Column(
            "online_payment_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {col["name"] for col in inspect(bind).get_columns("web_profiles")}
    if "online_payment_enabled" not in columns:
        return
    op.drop_column("web_profiles", "online_payment_enabled")
