"""Booking cancellation (notes + refund-flag logic)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Booking
from app.services import booking_notes as notes
from app.services.booking_shared import BookingError, BookingResult, _utcnow


async def cancel_booking(
    db: AsyncSession,
    booking_id: int,
    *,
    reason: str | None = None,
    admin_user_id: int | None = None,
) -> BookingResult:
    booking = (
        await db.execute(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )
    ).scalar_one_or_none()
    if booking is None:
        raise BookingError("Booking not found", status_code=404)
    if booking.status == "cancelled":
        raise BookingError("Booking is already cancelled")

    existing = booking.notes or ""
    booking.status = "cancelled"
    booking.updated_at = _utcnow()

    if reason:
        prefix = (
            notes.NOTE_ADMIN_CANCEL_PREFIX
            if admin_user_id
            else notes.NOTE_CANCEL_PREFIX
        )
        booking.notes = notes.append_note(existing, prefix + reason.strip())
        existing = booking.notes or ""

    # Ops signal for paid online cancels (plan matrix; also covers admin cancel path)
    if (
        booking.payment_method == "online_banking"
        and booking.payment_status == "paid"
        and booking.payment_transaction_id
        and not notes.notes_contain(existing, notes.NOTE_SEPAY_REFUND_PREFIX)
    ):
        booking.notes = notes.append_note(
            existing, notes.sepay_refund_note(booking.payment_transaction_id)
        )

    await db.flush()
    await db.refresh(booking)
    return BookingResult(
        booking=booking,
        email_action="cancellation",
        cancel_reason=reason,
    )
