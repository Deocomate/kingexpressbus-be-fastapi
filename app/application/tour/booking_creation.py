"""Tour booking creation + soft daily capacity (row-locked)."""

from __future__ import annotations

import secrets
import string
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.hotel.shared import BookingError, COUNTED_STATUSES, PAYMENT_METHODS, utcnow
from app.infrastructure.persistence.models import Tour, TourBooking


async def _generate_code(db: AsyncSession) -> str:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(8):
        code = "TR-" + "".join(secrets.choice(alphabet) for _ in range(12))
        exists = await db.scalar(
            select(func.count())
            .select_from(TourBooking)
            .where(TourBooking.booking_code == code)
        )
        if not exists:
            return code
    raise RuntimeError("Unable to generate unique tour booking code")


async def guests_booked(
    db: AsyncSession,
    *,
    tour_id: int,
    tour_date: date,
    exclude_booking_id: int | None = None,
    for_update: bool = False,
) -> int:
    stmt = select(func.coalesce(func.sum(TourBooking.guests), 0)).where(
        TourBooking.tour_id == tour_id,
        TourBooking.tour_date == tour_date,
        TourBooking.status.in_(COUNTED_STATUSES),
    )
    if exclude_booking_id is not None:
        stmt = stmt.where(TourBooking.id != exclude_booking_id)
    if for_update:
        stmt = stmt.with_for_update()
    return int(await db.scalar(stmt) or 0)


async def create_tour_booking(
    db: AsyncSession,
    *,
    tour_id: int,
    tour_date: date,
    guests: int,
    customer_name: str,
    customer_email: str | None,
    customer_phone: str | None,
    payment_method: str,
    total_price: int,
    notes: str | None = None,
    user_id: int | None = None,
) -> TourBooking:
    if payment_method not in PAYMENT_METHODS:
        raise BookingError("Invalid payment method")
    if guests < 1:
        raise BookingError("At least one guest is required")
    if tour_date < date.today():
        raise BookingError("Tour date cannot be in the past")

    tour = (
        await db.execute(select(Tour).where(Tour.id == tour_id).with_for_update())
    ).scalar_one_or_none()
    if tour is None or not tour.is_active:
        raise BookingError("Tour not found", status_code=404)

    booked = await guests_booked(
        db, tour_id=tour.id, tour_date=tour_date, for_update=True
    )
    available = max(0, int(tour.max_guests) - booked)
    if guests > available:
        raise BookingError(
            f"Only {available} seat(s) available on this date",
            status_code=409,
        )

    unit = int(tour.base_price)
    expected_total = unit * guests
    if int(total_price) != expected_total:
        raise BookingError(
            f"Price changed. Expected {expected_total}",
            status_code=409,
        )

    booking = TourBooking(
        booking_code=await _generate_code(db),
        user_id=user_id,
        tour_id=tour.id,
        tour_date=tour_date,
        guests=guests,
        unit_price=unit,
        total_price=expected_total,
        customer_name=customer_name.strip(),
        customer_email=(customer_email or "").strip() or None,
        customer_phone=(customer_phone or "").strip() or None,
        status="pending",
        payment_method=payment_method,
        payment_status="unpaid",
        notes=notes,
        tour_name_snapshot=tour.name,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(booking)
    await db.flush()
    await db.refresh(booking)
    return booking
