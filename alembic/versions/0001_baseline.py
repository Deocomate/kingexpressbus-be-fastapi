"""Baseline revision — create application schema from SQLAlchemy models.

Revision ID: 0001_baseline
Revises:
"""

from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

# Mail queue tables are added in 0002_mail_jobs.
_MAIL_TABLES = frozenset({"mail_jobs", "failed_mail_jobs"})


def upgrade() -> None:
    from app.infrastructure.persistence.base import Base
    import app.infrastructure.persistence.models  # noqa: F401

    tables = [t for t in Base.metadata.sorted_tables if t.name not in _MAIL_TABLES]
    Base.metadata.create_all(bind=op.get_bind(), tables=tables)


def downgrade() -> None:
    from app.infrastructure.persistence.base import Base
    import app.infrastructure.persistence.models  # noqa: F401

    tables = [t for t in Base.metadata.sorted_tables if t.name not in _MAIL_TABLES]
    Base.metadata.drop_all(bind=op.get_bind(), tables=tables)
