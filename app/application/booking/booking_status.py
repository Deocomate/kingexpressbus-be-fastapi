"""Booking status transitions (confirm/complete)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.booking import booking_notes as notes
from app.application.booking.booking_shared import (
    BookingError,
    BookingResult,
    EmailAction,
    _utcnow,
)
from app.infrastructure.persistence.models import Booking


async def update_booking_status(
    db: AsyncSession,
    booking_id: int,
    status: str,
    *,
    notes_text: str | None = None,
) -> BookingResult:
    booking = (
        await db.execute(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )
    ).scalar_one_or_none()
    if booking is None:
        raise BookingError("Booking not found", status_code=404)

    email_action: EmailAction = None
    is_pending_to_confirmed = status == "confirmed" and booking.status == "pending"

    booking.status = status
    booking.updated_at = _utcnow()

    if is_pending_to_confirmed:
        booking.confirmed_at = _utcnow()
        email_action = (
            "payment_request"
            if booking.payment_method == "online_banking"
            else "approval"
        )
    elif status == "cancelled":
        existing = booking.notes or ""
        to_append: list[str] = []
        if notes_text and not notes.notes_contain(
            existing,
            notes.NOTE_ADMIN_CANCEL_PREFIX,
            notes.LEGACY_NOTE_ADMIN_CANCEL_PREFIX,
        ):
            to_append.append(notes.NOTE_ADMIN_CANCEL_PREFIX + notes_text.strip())
        if (
            booking.payment_method == "online_banking"
            and booking.payment_status == "paid"
            and booking.payment_transaction_id
            and not notes.notes_contain(existing, notes.NOTE_SEPAY_REFUND_PREFIX)
        ):
            to_append.append(notes.sepay_refund_note(booking.payment_transaction_id))
        if to_append:
            booking.notes = notes.append_note(existing, "\n".join(to_append))
        email_action = "cancellation"

    await db.flush()
    await db.refresh(booking)
    return BookingResult(
        booking=booking,
        email_action=email_action,
        cancel_reason=notes_text if status == "cancelled" else None,
    )
