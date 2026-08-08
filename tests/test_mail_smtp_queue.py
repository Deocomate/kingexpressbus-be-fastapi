"""Focused tests for Gmail SMTP sender + MySQL mail queue (no full app)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.infrastructure.mail.mail import queue_booking_mail, send_booking_mail
from app.infrastructure.mail.mail_queue import (
    enqueue_mail_job,
    fail_or_retry_mail_job,
    process_mail_job,
)
from app.infrastructure.mail.mail_sender import RecordingMailSender, set_mail_sender


@pytest.mark.asyncio
async def test_smtp_failure_logged_not_raised() -> None:
    class Boom:
        async def send(self, *, to, subject, html):
            raise RuntimeError("smtp down")

    set_mail_sender(Boom())  # type: ignore[arg-type]
    try:
        ok = await send_booking_mail(
            kind="confirmation",
            details={
                "booking_id": 1,
                "booking_code": "X",
                "customer_email": "a@b.com",
                "customer_name": "A",
                "route_name": "R",
                "total_price": 1,
            },
            settings=Settings(),
        )
        assert ok is False
    finally:
        set_mail_sender(None)


@pytest.mark.asyncio
async def test_recording_mail_sender_includes_admin() -> None:
    rec = RecordingMailSender()
    set_mail_sender(rec)
    try:
        assert await send_booking_mail(
            kind="approval",
            details={
                "booking_id": 1,
                "booking_code": "X",
                "customer_email": "a@b.com",
                "customer_name": "A",
                "route_name": "R",
                "total_price": 1,
            },
            settings=Settings(admin_notify_email="admin@example.com"),
        )
        assert len(rec.sent) == 1
        assert "a@b.com" in rec.sent[0]["to"]
        assert "admin@example.com" in rec.sent[0]["to"]
    finally:
        set_mail_sender(None)


@pytest.mark.asyncio
async def test_enqueue_mail_job_persists_payload() -> None:
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    job = await enqueue_mail_job(
        db,
        to=["a@b.com"],
        subject="Hi",
        html="<p>x</p>",
        booking_id=9,
        kind="confirmation",
    )
    assert db.add.called
    added = db.add.call_args[0][0]
    assert added.payload["to"] == ["a@b.com"]
    assert added.payload["booking_id"] == 9
    assert added.payload["kind"] == "confirmation"
    db.commit.assert_awaited()
    assert job is added


@pytest.mark.asyncio
async def test_process_mail_job_success_deletes() -> None:
    rec = RecordingMailSender()
    job = SimpleNamespace(
        id=1,
        payload={"to": ["a@b.com"], "subject": "S", "html": "<b>h</b>"},
        attempts=1,
    )
    db = AsyncMock()
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    ok = await process_mail_job(
        db, job, settings=Settings(), sender=rec  # type: ignore[arg-type]
    )
    assert ok is True
    assert len(rec.sent) == 1
    db.delete.assert_awaited_with(job)


@pytest.mark.asyncio
async def test_fail_or_retry_moves_to_failed_after_max() -> None:
    settings = Settings(mail_max_attempts=2)
    job = SimpleNamespace(
        id=3,
        payload={"to": ["a@b.com"], "subject": "S", "html": "h"},
        attempts=2,
        reserved_at="x",
        last_error=None,
        available_at=None,
    )
    db = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    await fail_or_retry_mail_job(db, job, error="boom", settings=settings)
    assert db.add.called
    failed = db.add.call_args[0][0]
    assert failed.payload == job.payload
    assert "boom" in (failed.error or "")
    db.delete.assert_awaited_with(job)


@pytest.mark.asyncio
async def test_queue_booking_mail_prepare_miss_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    db = AsyncMock()
    from app.infrastructure.mail import mail as mail_svc

    monkeypatch.setattr(
        mail_svc,
        "prepare_mail_details",
        AsyncMock(return_value=None),
    )
    ok = await queue_booking_mail(
        db,
        booking_id=99,
        kind="confirmation",
        settings=Settings(),
    )
    assert ok is False
