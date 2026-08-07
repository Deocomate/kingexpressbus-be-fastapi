"""Booking creation + admin field-edit flow (availability checks, code generation).

Slightly over the ~200-line guideline (235) intentionally: booking_edit.py reuses
this file's stop-validation helper, and the create flow is one atomic transaction
(availability check -> pricing -> code generation -> insert) that doesn't have a
clean split seam.
"""

from __future__ import annotations

import logging
import secrets
import string
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Booking, Bus, Route, RouteStop, Trip, TripBlock
from app.services import booking_notes as notes
from app.services.booking_shared import (
    COUNTED_STATUSES,
    BookingError,
    PriceChangedError,
    _utcnow,
)
from app.services.pricing import resolve_effective_price
from app.services.seats import available_seats

logger = logging.getLogger(__name__)


async def _generate_booking_code(db: AsyncSession) -> str:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(5):
        code = "".join(secrets.choice(alphabet) for _ in range(16))
        exists = await db.scalar(
            select(func.count()).select_from(Booking).where(Booking.booking_code == code)
        )
        if not exists:
            return code
    raise RuntimeError("Unable to generate unique booking code")


async def validate_stop_selections(
    db: AsyncSession,
    *,
    trip_id: int,
    is_hotel_pickup: bool,
    pickup_stop_id: int | None,
    dropoff_stop_id: int,
) -> None:
    row = (
        await db.execute(
            select(Trip.route_id, Trip.is_active, Route.available_hotel_pickup)
            .join(Route, Trip.route_id == Route.id)
            .where(Trip.id == trip_id)
        )
    ).one_or_none()
    if row is None or not row.is_active:
        raise BookingError("Trip not found or inactive")
    if is_hotel_pickup and not bool(row.available_hotel_pickup):
        raise BookingError("Hotel pickup is not available on this route")

    stop_ids = [dropoff_stop_id]
    if not is_hotel_pickup and pickup_stop_id is not None:
        stop_ids.append(pickup_stop_id)

    result = await db.execute(
        select(RouteStop.stop_id, RouteStop.stop_type).where(
            RouteStop.route_id == row.route_id,
            RouteStop.stop_id.in_(list(set(stop_ids))),
        )
    )
    by_stop: dict[int, list[str]] = {}
    for sid, stype in result.all():
        by_stop.setdefault(int(sid), []).append(str(stype))

    def allowed(stop_id: int, types: set[str]) -> bool:
        return any(t in types for t in by_stop.get(stop_id, []))

    if not is_hotel_pickup and pickup_stop_id is not None:
        if not allowed(pickup_stop_id, {"pickup", "both"}):
            raise BookingError("Invalid pickup stop for this route")
    if not allowed(dropoff_stop_id, {"dropoff", "both"}):
        raise BookingError("Invalid dropoff stop for this route")


async def create_booking(
    db: AsyncSession,
    *,
    trip_id: int,
    booking_date: date,
    quantity: int,
    customer_name: str,
    customer_phone: str,
    customer_email: str,
    dropoff_stop_id: int,
    total_price: int,
    payment_method: str,
    pickup_stop_id: int | None = None,
    is_hotel_pickup: bool = False,
    hotel_pickup_address: str | None = None,
    notes_text: str | None = None,
    user_id: int | None = None,
) -> Booking:
    """Create pending booking. Rejects price mismatch before taking locks."""
    if payment_method not in ("cash_on_pickup", "online_banking"):
        raise BookingError("Invalid payment method")
    if quantity < 1:
        raise BookingError("Quantity must be at least 1")

    await validate_stop_selections(
        db,
        trip_id=trip_id,
        is_hotel_pickup=is_hotel_pickup,
        pickup_stop_id=pickup_stop_id,
        dropoff_stop_id=dropoff_stop_id,
    )

    if is_hotel_pickup:
        if not (hotel_pickup_address and hotel_pickup_address.strip()):
            raise BookingError("Hotel pickup address is required")
    elif pickup_stop_id is None:
        raise BookingError("Pickup stop is required unless hotel pickup")

    breakdown = await resolve_effective_price(db, trip_id=trip_id, booking_date=booking_date)
    server_total = int(breakdown["final_unit_price"]) * quantity
    if int(total_price) != server_total:
        logger.warning(
            "Client submitted booking total differs from server calculation",
            extra={
                "trip_id": trip_id,
                "booking_date": booking_date.isoformat(),
                "submitted_total_price": int(total_price),
                "server_total_price": server_total,
            },
        )
        raise PriceChangedError(
            submitted_total=int(total_price),
            breakdown={
                **breakdown,
                "quantity": quantity,
                "server_total": server_total,
                "total_surcharge_amount": int(breakdown["total_surcharge_unit"]) * quantity,
            },
            server_total=server_total,
        )

    # Capacity transaction with locks (Laravel lockForUpdate semantics)
    trip_row = (
        await db.execute(
            select(Bus.seat_count, Trip.is_active)
            .select_from(Trip)
            .join(Bus, Trip.bus_id == Bus.id)
            .where(Trip.id == trip_id)
            .with_for_update()
        )
    ).one_or_none()
    if trip_row is None or not trip_row.is_active:
        raise BookingError("Trip not found or inactive")

    block = (
        await db.execute(
            select(TripBlock)
            .where(
                TripBlock.trip_id == trip_id,
                TripBlock.start_date <= booking_date,
                TripBlock.end_date >= booking_date,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    block_type = block.block_type if block else None
    if block_type in ("sold_out", "off_day"):
        raise BookingError("Trip is blocked for this date")

    booked_qty = int(
        await db.scalar(
            select(func.coalesce(func.sum(Booking.quantity), 0))
            .where(
                Booking.trip_id == trip_id,
                Booking.booking_date == booking_date,
                Booking.status.in_(COUNTED_STATUSES),
            )
            .with_for_update()
        )
        or 0
    )
    avail = available_seats(
        seat_count=int(trip_row.seat_count),
        booked_quantity=booked_qty,
        block_type=block_type,
    )
    if quantity > avail:
        raise BookingError(
            f"Not enough seats: requested {quantity}, available {avail}"
        )

    customer_notes = notes.strip_user_text(notes_text)
    final_pickup: int | None = pickup_stop_id
    booking_notes_value: str | None = customer_notes
    if is_hotel_pickup:
        addr = notes.strip_user_text(hotel_pickup_address) or ""
        booking_notes_value = notes.build_hotel_pickup_notes(
            hotel_address=addr,
            customer_notes=customer_notes,
        )
        final_pickup = None

    code = await _generate_booking_code(db)
    now = _utcnow()
    booking = Booking(
        booking_code=code,
        user_id=user_id,
        trip_id=trip_id,
        booking_date=booking_date,
        customer_name=customer_name.strip(),
        customer_email=customer_email.strip(),
        customer_phone=customer_phone.strip(),
        pickup_stop_id=final_pickup,
        dropoff_stop_id=dropoff_stop_id,
        quantity=quantity,
        base_unit_price=int(breakdown["base_unit_price"]),
        global_surcharge_unit=int(breakdown["global_surcharge_unit"]),
        route_surcharge_unit=int(breakdown["route_surcharge_unit"]),
        final_unit_price=int(breakdown["final_unit_price"]),
        total_surcharge_amount=int(breakdown["total_surcharge_unit"]) * quantity,
        total_price=server_total,
        surcharge_reason_snapshot=breakdown.get("surcharge_reason_snapshot"),
        status="pending",
        payment_method=payment_method,
        payment_status="unpaid",
        notes=booking_notes_value,
        created_at=now,
        updated_at=now,
    )
    db.add(booking)
    await db.flush()
    await db.refresh(booking)
    return booking
