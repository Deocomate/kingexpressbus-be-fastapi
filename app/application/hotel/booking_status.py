"""Hotel booking status transitions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.hotel.shared import BookingError, EmailAction, ServiceBookingResult, utcnow
from app.infrastructure.persistence.models import HotelBooking


async def update_hotel_booking_status(
    db: AsyncSession,
    booking_id: int,
    status: str,
    *,
    notes_text: str | None = None,
) -> ServiceBookingResult:
    booking = (
        await db.execute(
            select(HotelBooking).where(HotelBooking.id == booking_id).with_for_update()
        )
    ).scalar_one_or_none()
    if booking is None:
        raise BookingError("Hotel booking not found", status_code=404)

    email_action: EmailAction = None
    if status == "confirmed" and booking.status == "pending":
        booking.confirmed_at = utcnow()
        email_action = "approval"
    elif status == "cancelled":
        if notes_text:
            prefix = "[Admin cancel] "
            note = prefix + notes_text.strip()
            booking.notes = f"{booking.notes}\n{note}".strip() if booking.notes else note
        email_action = "cancellation"

    booking.status = status
    booking.updated_at = utcnow()
    await db.flush()
    await db.refresh(booking)
    return ServiceBookingResult(
        booking=booking,
        email_action=email_action,
        cancel_reason=notes_text if status == "cancelled" else None,
    )
