"""Shared helpers for the public booking + payment route groups (signed URLs, mail)."""

from __future__ import annotations

from app.core.config import Settings
from app.infrastructure.mail import mail as mail_svc
from app.infrastructure.persistence.session import AsyncSessionLocal
from app.infrastructure.storage import signed_urls
from app.presentation.schemas.booking import BookingOut


def issue_success_url(settings: Settings, booking_id: int) -> str:
    """Mint signed success URL — only from create / SePay return (not a public getter)."""
    base = settings.frontend_base_url.rstrip("/") + settings.success_path_template
    return signed_urls.sign_success_url(
        base_url=base,
        booking_id=booking_id,
        signing_key=settings.success_url_signing_key,
    )


def success_path_template(settings: Settings) -> str:
    return settings.frontend_base_url.rstrip("/") + settings.success_path_template


def booking_out(booking, success_url: str | None = None) -> BookingOut:
    data = BookingOut.model_validate(booking)
    if success_url:
        data.success_url = success_url
    return data


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
