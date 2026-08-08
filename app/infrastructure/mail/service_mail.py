"""Hotel / tour booking mail queue helpers."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.infrastructure.mail import mail_queue
from app.infrastructure.mail.mail_formatters import (
    absolute_url,
    customer_display,
    format_booking_date,
    format_vnd,
)
from app.infrastructure.mail.mail_sender import MailSender, get_mail_sender
from app.infrastructure.mail.mail_templates import render_service_booking_mail
from app.infrastructure.persistence.models import HotelBooking, TourBooking, WebProfile

logger = logging.getLogger(__name__)

ServiceKind = Literal["hotel", "tour"]


_PAYMENT_LABELS = {
    "cash_at_property": "Thanh toán tại chỗ / Pay at property",
    "bank_transfer": "Chuyển khoản thủ công / Manual bank transfer",
}


def _copyright_year(settings: Settings) -> int:
    try:
        return datetime.now(ZoneInfo(settings.app_timezone)).year
    except Exception:
        return datetime.now().year


async def _web_profile_bits(db: AsyncSession, settings: Settings) -> dict[str, Any]:
    profile = (
        await db.execute(
            select(WebProfile).where(WebProfile.is_default.is_(True)).limit(1)
        )
    ).scalar_one_or_none()
    return {
        "web_title": (profile.title if profile else None) or "King Express Bus",
        "web_phone": (profile.hotline or profile.phone) if profile else None,
        "logo_url": absolute_url(profile.logo_url if profile else None, settings.frontend_base_url),
        "website_url": settings.frontend_base_url.rstrip("/"),
        "copyright_year": _copyright_year(settings),
    }


async def prepare_hotel_mail_details(
    db: AsyncSession, booking_id: int, settings: Settings
) -> dict[str, Any] | None:
    booking = await db.get(HotelBooking, booking_id)
    if booking is None:
        return None
    bits = await _web_profile_bits(db, settings)
    return {
        **bits,
        "service_kind": "hotel",
        "booking_id": booking.id,
        "booking_code": booking.booking_code,
        "customer_name": booking.customer_name,
        "customer_email": booking.customer_email,
        "customer_phone": booking.customer_phone,
        "customer_display": customer_display(booking.customer_name, booking.customer_phone),
        "hotel_name": booking.hotel_name_snapshot,
        "room_name": booking.room_name_snapshot,
        "check_in": format_booking_date(booking.check_in),
        "check_out": format_booking_date(booking.check_out),
        "nights": booking.nights,
        "rooms_count": booking.rooms_count,
        "adults": booking.adults,
        "children": booking.children,
        "breakfast_count": booking.breakfast_count,
        "total_price": format_vnd(booking.total_price),
        "payment_method_label": _PAYMENT_LABELS.get(
            booking.payment_method, booking.payment_method
        ),
        "status": booking.status,
    }


async def prepare_tour_mail_details(
    db: AsyncSession, booking_id: int, settings: Settings
) -> dict[str, Any] | None:
    booking = await db.get(TourBooking, booking_id)
    if booking is None:
        return None
    bits = await _web_profile_bits(db, settings)
    return {
        **bits,
        "service_kind": "tour",
        "booking_id": booking.id,
        "booking_code": booking.booking_code,
        "customer_name": booking.customer_name,
        "customer_email": booking.customer_email,
        "customer_phone": booking.customer_phone,
        "customer_display": customer_display(booking.customer_name, booking.customer_phone),
        "tour_name": booking.tour_name_snapshot,
        "tour_date": format_booking_date(booking.tour_date),
        "guests": booking.guests,
        "total_price": format_vnd(booking.total_price),
        "payment_method_label": _PAYMENT_LABELS.get(
            booking.payment_method, booking.payment_method
        ),
        "status": booking.status,
    }


async def queue_service_booking_mail(
    db: AsyncSession,
    *,
    service_kind: ServiceKind,
    booking_id: int,
    kind: str,
    settings: Settings,
    cancel_reason: str | None = None,
    sender: MailSender | None = None,
) -> bool:
    if service_kind == "hotel":
        details = await prepare_hotel_mail_details(db, booking_id, settings)
    else:
        details = await prepare_tour_mail_details(db, booking_id, settings)
    if not details:
        logger.error("Cannot prepare %s mail data: %s", service_kind, booking_id)
        return False
    if cancel_reason:
        details["cancel_reason"] = cancel_reason

    email = details.get("customer_email")
    if not email:
        logger.error("Cannot send %s mail: missing customer email", service_kind)
        return False
    recipients = [str(email)]
    if settings.admin_notify_email:
        recipients.append(settings.admin_notify_email)

    try:
        subject, html = render_service_booking_mail(kind, details)
        await mail_queue.enqueue_mail_job(
            db,
            to=recipients,
            subject=subject,
            html=html,
            booking_id=None,
            kind=f"{service_kind}_{kind}",
        )
        if settings.mail_queue_inline:
            await mail_queue.process_one_available(
                db, settings=settings, sender=sender or get_mail_sender(settings)
            )
        return True
    except Exception:
        logger.exception(
            "Error while queueing %s %s email",
            service_kind,
            kind,
            extra={"booking_id": booking_id},
        )
        return False
