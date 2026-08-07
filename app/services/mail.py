"""Booking mail content (detail lookup + rendering) — failures must not roll back bookings."""

from __future__ import annotations

import logging
from html import escape
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import Booking, Bus, Route, Stop, Trip, WebProfile
from app.services.booking_notes import extract_hotel_pickup_address
from app.services import mail_queue
from app.services.mail_sender import MailSender, get_mail_sender

logger = logging.getLogger(__name__)


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
    if booking.pickup_stop_id is None and hotel:
        pickup_info = f"Hotel pickup: {hotel}"
    else:
        pickup_info = f"{pickup_name or 'N/A'} - {pickup_address or 'N/A'}"

    payment_url = (
        f"{settings.frontend_base_url.rstrip('/')}"
        f"/dat-ve/chuyen-huong-sepay/{booking.booking_code}"
    )

    return {
        "booking_id": booking.id,
        "booking_code": booking.booking_code,
        "customer_name": booking.customer_name,
        "customer_email": booking.customer_email,
        "customer_phone": booking.customer_phone,
        "booking_date": booking.booking_date.isoformat(),
        "quantity": booking.quantity,
        "total_price": booking.total_price,
        "status": booking.status,
        "payment_method": booking.payment_method,
        "payment_status": booking.payment_status,
        "route_name": row.route_name,
        "start_time": str(row.start_time)[:5] if row.start_time else "",
        "bus_name": row.bus_name,
        "bus_model_name": row.bus_model_name,
        "pickup_info": pickup_info,
        "dropoff_info": f"{row.dropoff_name} - {row.dropoff_address or ''}",
        "web_title": (profile.title if profile else None) or settings.app_name,
        "web_phone": (profile.hotline or profile.phone) if profile else "",
        "web_email": profile.email if profile else "",
        "payment_url": payment_url,
        "cancel_reason": None,
    }


def _safe(value: Any) -> str:
    return escape(str(value if value is not None else ""))


def _render_simple(kind: str, details: dict[str, Any]) -> tuple[str, str]:
    code = _safe(details.get("booking_code"))
    name = _safe(details.get("customer_name"))
    route = _safe(details.get("route_name"))
    total = _safe(details.get("total_price"))
    subjects = {
        "confirmation": f"Booking confirmation {code}",
        "payment_request": f"Payment request {code}",
        "approval": f"Booking approved {code}",
        "cancellation": f"Booking cancelled {code}",
    }
    subject = subjects[kind]
    extra = ""
    if kind == "payment_request":
        extra = f'<p><a href="{_safe(details.get("payment_url"))}">Pay with SePay</a></p>'
    if kind == "cancellation":
        extra = f"<p>Reason: {_safe(details.get('cancel_reason') or 'N/A')}</p>"
    html = f"""
    <div>
      <h1>{_safe(subject)}</h1>
      <p>Customer: {name}</p>
      <p>Route: {route}</p>
      <p>Total: {total} VND</p>
      {extra}
    </div>
    """
    return subject, html


def _recipients(details: dict[str, Any], settings: Settings) -> list[str] | None:
    email = details.get("customer_email")
    if not email:
        return None
    recipients = [str(email)]
    admin = settings.admin_notify_email
    if admin and admin not in recipients:
        recipients.append(admin)
    return recipients


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
        subject, html = _render_simple(kind, details)
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
        subject, html = _render_simple(kind, details)
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
