"""Shared helpers for the admin booking route group (mail dispatch, response shaping)."""

from __future__ import annotations

from app.core.config import Settings
from app.infrastructure.mail import mail as mail_svc
from app.infrastructure.persistence.session import AsyncSessionLocal
from app.presentation.schemas.booking import BookingOut


async def bg_mail(
    booking_id: int,
    kind: str,
    settings: Settings,
    cancel_reason: str | None = None,
) -> None:
    async with AsyncSessionLocal() as session:
        await mail_svc.queue_booking_mail(
            session,
            booking_id=booking_id,
            kind=kind,
            settings=settings,
            cancel_reason=cancel_reason,
        )


def booking_out(booking) -> BookingOut:
    return BookingOut.model_validate(booking)
