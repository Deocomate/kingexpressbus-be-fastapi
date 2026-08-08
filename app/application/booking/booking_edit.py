"""Admin booking field edits (customer/stop/quantity/notes — not status)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.booking import booking_notes as notes
from app.application.booking.booking_creation import validate_stop_selections
from app.application.booking.booking_shared import (
    COUNTED_STATUSES,
    BookingError,
    _utcnow,
)
from app.application.booking.seats import available_seats
from app.infrastructure.persistence.models import Booking, Bus, Trip, TripBlock


async def update_booking_fields(
    db: AsyncSession,
    booking_id: int,
    *,
    customer_name: str,
    customer_phone: str,
    customer_email: str | None,
    pickup_stop_id: int | None,
    dropoff_stop_id: int,
    quantity: int,
    notes_text: str | None,
    hotel_pickup_address: str | None = None,
) -> Booking:
    """Admin edit — customer/stop/quantity/notes only.

    status/payment_status/confirmed_at/payment_transaction_id are deliberately
    excluded (see plan.md price-authority decision + phase-8 spec) — those
    move only through the confirm/cancel/complete/status action endpoints so
    the mail + confirmed_at + refund-note side effects always fire. Price is
    server-recomputed from the existing final_unit_price * new quantity, never
    accepted from the client, matching the create-path price authority rule.

    pickup_stop_id=None means hotel pickup: `notes` is the sole storage for
    the pickup address (encoded via build_hotel_pickup_notes, read back via
    extract_hotel_pickup_address in mail.py) — never overwrite it with the
    raw free-text notes_text, or the address silently disappears from every
    booking confirmation/email that reads it afterward.
    """
    booking = (
        await db.execute(select(Booking).where(Booking.id == booking_id).with_for_update())
    ).scalar_one_or_none()
    if booking is None:
        raise BookingError("Booking not found", status_code=404)
    if booking.status in ("cancelled", "completed"):
        raise BookingError("Cannot edit a completed or cancelled booking")
    if quantity < 1:
        raise BookingError("Quantity must be at least 1")
    if pickup_stop_id is None and not (hotel_pickup_address and hotel_pickup_address.strip()):
        raise BookingError("Hotel pickup address is required")

    await validate_stop_selections(
        db,
        trip_id=booking.trip_id,
        is_hotel_pickup=pickup_stop_id is None,
        pickup_stop_id=pickup_stop_id,
        dropoff_stop_id=dropoff_stop_id,
    )

    if quantity != booking.quantity:
        trip_row = (
            await db.execute(
                select(Bus.seat_count, Trip.is_active)
                .select_from(Trip)
                .join(Bus, Trip.bus_id == Bus.id)
                .where(Trip.id == booking.trip_id)
                .with_for_update()
            )
        ).one_or_none()
        if trip_row is None or not trip_row.is_active:
            raise BookingError("Trip not found or inactive")
        block = (
            await db.execute(
                select(TripBlock)
                .where(
                    TripBlock.trip_id == booking.trip_id,
                    TripBlock.start_date <= booking.booking_date,
                    TripBlock.end_date >= booking.booking_date,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        block_type = block.block_type if block else None
        other_booked_qty = int(
            await db.scalar(
                select(func.coalesce(func.sum(Booking.quantity), 0))
                .where(
                    Booking.trip_id == booking.trip_id,
                    Booking.booking_date == booking.booking_date,
                    Booking.status.in_(COUNTED_STATUSES),
                    Booking.id != booking_id,
                )
                .with_for_update()
            )
            or 0
        )
        avail = available_seats(
            seat_count=int(trip_row.seat_count),
            booked_quantity=other_booked_qty,
            block_type=block_type,
        )
        if quantity > avail:
            raise BookingError(f"Not enough seats: requested {quantity}, available {avail}")
        booking.total_surcharge_amount = booking.route_surcharge_unit * quantity + (
            booking.global_surcharge_unit * quantity
        )
        booking.total_price = booking.final_unit_price * quantity
        booking.quantity = quantity

    customer_notes = notes.strip_user_text(notes_text)
    if pickup_stop_id is None:
        booking.notes = notes.build_hotel_pickup_notes(
            hotel_address=hotel_pickup_address or "",
            customer_notes=customer_notes,
        )
    else:
        booking.notes = customer_notes

    booking.customer_name = customer_name.strip()
    booking.customer_phone = customer_phone.strip()
    booking.customer_email = customer_email.strip() if customer_email else None
    booking.dropoff_stop_id = dropoff_stop_id
    booking.pickup_stop_id = pickup_stop_id
    booking.updated_at = _utcnow()

    await db.flush()
    await db.refresh(booking)
    return booking
