"""Booking mail content (detail lookup + rendering) — failures must not roll back bookings."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.booking.booking_notes import extract_hotel_pickup_address
from app.core.config import Settings
from app.infrastructure.mail import mail_queue
from app.infrastructure.mail.mail_formatters import (
    absolute_url,
    customer_display,
    format_booking_date,
    format_pickup_info,
    format_vnd,
    payment_method_label,
    quantity_label,
    ticket_type,
)
from app.infrastructure.mail.mail_sender import MailSender, get_mail_sender
from app.infrastructure.mail.mail_templates import render_booking_mail
from app.infrastructure.persistence.models import (
    Booking,
    Bus,
    Route,
    Stop,
    Trip,
    WebProfile,
)

logger = logging.getLogger(__name__)


def _copyright_year(settings: Settings) -> int:
    try:
        return datetime.now(ZoneInfo(settings.app_timezone)).year
    except Exception:
        return datetime.now().year


async def prepare_mail_details(
    db: AsyncSession,
    booking_id: int,
    settings: Settings,
) -> dict[str, Any] | None:
    row = (
        await db.execute(
            select(
                Booking,
                Route.name.label("route_name"),
                Trip.start_time,
                Bus.name.label("bus_name"),
                Bus.model_name.label("bus_model_name"),
                Stop.name.label("dropoff_name"),
                Stop.address.label("dropoff_address"),
            )
            .select_from(Booking)
            .join(Trip, Booking.trip_id == Trip.id)
            .join(Bus, Trip.bus_id == Bus.id)
            .join(Route, Trip.route_id == Route.id)
            .join(Stop, Booking.dropoff_stop_id == Stop.id)
            .where(Booking.id == booking_id)
        )
    ).one_or_none()
    if row is None:
        return None

    booking: Booking = row[0]
    pickup_name = None
    pickup_address = None
    if booking.pickup_stop_id:
        pickup = await db.get(Stop, booking.pickup_stop_id)
        if pickup:
            pickup_name = pickup.name
            pickup_address = pickup.address

    profile = (
        await db.execute(
            select(WebProfile).where(WebProfile.is_default.is_(True)).limit(1)
        )
    ).scalar_one_or_none()

    hotel = extract_hotel_pickup_address(booking.notes)
    pickup_info = format_pickup_info(
        pickup_stop_id=booking.pickup_stop_id,
        pickup_name=pickup_name,
        pickup_address=pickup_address,
        hotel_address=hotel,
    )

    payment_url = (
        f"{settings.frontend_base_url.rstrip('/')}"
        f"/dat-ve/chuyen-huong-sepay/{booking.booking_code}"
    )

    website_url = settings.frontend_base_url.rstrip("/")
    logo_raw = profile.logo_url if profile else None
    name = booking.customer_name
    phone = booking.customer_phone

    return {
        "booking_id": booking.id,
        "booking_code": booking.booking_code,
        "customer_name": name,
        "customer_email": booking.customer_email,
        "customer_phone": phone,
        "customer_display": customer_display(name, phone),
        "booking_date": booking.booking_date.isoformat(),
        "booking_date_display": format_booking_date(booking.booking_date),
        "quantity": booking.quantity,
        "quantity_label": quantity_label(booking.quantity),
        "total_price": booking.total_price,
        "total_price_display": format_vnd(booking.total_price),
        "status": booking.status,
        "payment_method": booking.payment_method,
        "payment_method_label": payment_method_label(booking.payment_method),
        "payment_status": booking.payment_status,
        "route_name": row.route_name,
        "start_time": str(row.start_time)[:5] if row.start_time else "",
        "bus_name": row.bus_name,
        "bus_model_name": row.bus_model_name,
        "ticket_type": ticket_type(row.bus_model_name, row.bus_name),
        "pickup_info": pickup_info,
        "dropoff_info": f"{row.dropoff_name} - {row.dropoff_address or ''}".rstrip(" -"),
        "web_title": (profile.title if profile else None) or settings.app_name,
        "web_phone": (profile.hotline or profile.phone) if profile else "",
        "web_email": profile.email if profile else "",
        "logo_url": absolute_url(logo_raw, website_url),
        "website_url": website_url,
        "copyright_year": _copyright_year(settings),
        "payment_url": payment_url,
        "cancel_reason": None,
    }


async def send_booking_mail(
    *,
    kind: str,
    details: dict[str, Any],
    settings: Settings,
    sender: MailSender | None = None,
) -> bool:
    """Send immediately via transport (tests / direct use). Prefer queue_booking_mail."""
    recipients = _recipients(details, settings)
    if not recipients:
        logger.error("Cannot send booking mail: missing customer email")
        return False
    try:
        mailer = sender or get_mail_sender(settings)
        subject, html = render_booking_mail(kind, details)
        await mailer.send(to=recipients, subject=subject, html=html)
        return True
    except Exception:
        logger.exception(
            "Error while sending booking %s email",
            kind,
            extra={"booking_id": details.get("booking_id")},
        )
        return False


async def queue_booking_mail(
    db: AsyncSession,
    *,
    booking_id: int,
    kind: str,
    settings: Settings,
    cancel_reason: str | None = None,
    sender: MailSender | None = None,
) -> bool:
    """Prepare, enqueue to mail_jobs, optionally process inline."""
    details = await prepare_mail_details(db, booking_id, settings)
    if not details:
        logger.error("Cannot prepare booking mail data: %s", booking_id)
        return False
    if cancel_reason:
        details["cancel_reason"] = cancel_reason

    recipients = _recipients(details, settings)
    if not recipients:
        logger.error("Cannot send booking mail: missing customer email")
        return False

    try:
        subject, html = render_booking_mail(kind, details)
        await mail_queue.enqueue_mail_job(
            db,
            to=recipients,
            subject=subject,
            html=html,
            booking_id=int(details.get("booking_id") or booking_id),
            kind=kind,
        )
        if settings.mail_queue_inline:
            await mail_queue.process_one_available(
                db, settings=settings, sender=sender
            )
        return True
    except Exception:
        logger.exception(
            "Error while queueing booking %s email",
            kind,
            extra={"booking_id": booking_id},
        )
        return False


def _recipients(details: dict[str, Any], settings: Settings) -> list[str] | None:
    email = details.get("customer_email")
    if not email:
        return None
    recipients = [str(email)]
    admin = settings.admin_notify_email
    if admin and admin not in recipients:
        recipients.append(admin)
    return recipients
