"""Mail job queue tables (Gmail SMTP durable queue)."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base


class MailJob(Base):
    __tablename__ = "mail_jobs"
    __table_args__ = (Index("ix_mail_jobs_queue_available", "queue", "available_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    queue: Mapped[str] = mapped_column(String(64), default="mail")
    payload: Mapped[Any] = mapped_column(JSON)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    reserved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FailedMailJob(Base):
    __tablename__ = "failed_mail_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    payload: Mapped[Any] = mapped_column(JSON)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
