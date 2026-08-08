"""Durable MySQL mail job queue."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.infrastructure.mail.mail_sender import MailSender, get_mail_sender
from app.infrastructure.persistence.models import FailedMailJob, MailJob

logger = logging.getLogger(__name__)

QUEUE_NAME = "mail"


def _utcnow() -> datetime:
    # Strip microseconds: MySQL DATETIME (no fsp) rounds .5s+ up a second, so a
    # just-enqueued job can look 1s in the future and miss inline claim.
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


async def enqueue_mail_job(
    db: AsyncSession,
    *,
    to: list[str],
    subject: str,
    html: str,
    booking_id: int | None = None,
    kind: str | None = None,
) -> MailJob:
    job = MailJob(
        queue=QUEUE_NAME,
        payload={
            "to": to,
            "subject": subject,
            "html": html,
            "booking_id": booking_id,
            "kind": kind,
        },
        attempts=0,
        available_at=_utcnow(),
        created_at=_utcnow(),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def claim_next_mail_job(
    db: AsyncSession,
    *,
    queue: str = QUEUE_NAME,
) -> MailJob | None:
    now = _utcnow()
    result = await db.execute(
        select(MailJob)
        .where(
            MailJob.queue == queue,
            MailJob.available_at <= now,
            MailJob.reserved_at.is_(None),
        )
        .order_by(MailJob.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None
    job.reserved_at = now
    job.attempts = int(job.attempts or 0) + 1
    await db.commit()
    await db.refresh(job)
    return job


async def complete_mail_job(db: AsyncSession, job: MailJob) -> None:
    await db.delete(job)
    await db.commit()


async def fail_or_retry_mail_job(
    db: AsyncSession,
    job: MailJob,
    *,
    error: str,
    settings: Settings,
) -> None:
    max_attempts = max(1, settings.mail_max_attempts)
    if job.attempts >= max_attempts:
        db.add(
            FailedMailJob(
                payload=job.payload,
                error=error[:4000],
                failed_at=_utcnow(),
            )
        )
        await db.delete(job)
        await db.commit()
        logger.error(
            "Mail job moved to failed_mail_jobs",
            extra={"job_id": job.id, "attempts": job.attempts, "error": error},
        )
        return

    backoff_seconds = min(300, 15 * (2 ** max(0, job.attempts - 1)))
    job.reserved_at = None
    job.last_error = error[:4000]
    job.available_at = _utcnow() + timedelta(seconds=backoff_seconds)
    await db.commit()
    logger.warning(
        "Mail job scheduled for retry",
        extra={
            "job_id": job.id,
            "attempts": job.attempts,
            "backoff_seconds": backoff_seconds,
        },
    )


async def process_mail_job(
    db: AsyncSession,
    job: MailJob,
    *,
    settings: Settings,
    sender: MailSender | None = None,
) -> bool:
    payload: dict[str, Any] = job.payload if isinstance(job.payload, dict) else {}
    to = list(payload.get("to") or [])
    subject = str(payload.get("subject") or "")
    html = str(payload.get("html") or "")
    if not to or not subject:
        await fail_or_retry_mail_job(
            db, job, error="Invalid payload: missing to/subject", settings=settings
        )
        return False

    mailer = sender or get_mail_sender(settings)
    try:
        await mailer.send(to=to, subject=subject, html=html)
    except Exception as exc:
        await fail_or_retry_mail_job(db, job, error=str(exc), settings=settings)
        return False

    await complete_mail_job(db, job)
    return True


async def process_one_available(
    db: AsyncSession,
    *,
    settings: Settings,
    sender: MailSender | None = None,
) -> bool:
    """Claim and send one job. Returns True if a job was claimed."""
    job = await claim_next_mail_job(db)
    if job is None:
        return False
    await process_mail_job(db, job, settings=settings, sender=sender)
    return True
