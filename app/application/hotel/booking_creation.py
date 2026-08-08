"""Hotel booking creation + soft room inventory (row-locked)."""

from __future__ import annotations

import secrets
import string
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.hotel.shared import BookingError, COUNTED_STATUSES, PAYMENT_METHODS, utcnow
from app.infrastructure.persistence.models import Hotel, HotelBooking, HotelRoom


async def _generate_code(db: AsyncSession) -> str:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(8):
        code = "HT-" + "".join(secrets.choice(alphabet) for _ in range(12))
        exists = await db.scalar(
            select(func.count())
            .select_from(HotelBooking)
            .where(HotelBooking.booking_code == code)
        )
        if not exists:
            return code
    raise RuntimeError("Unable to generate unique hotel booking code")


async def rooms_booked(
    db: AsyncSession,
    *,
    room_id: int,
    check_in: date,
    check_out: date,
    exclude_booking_id: int | None = None,
    for_update: bool = False,
) -> int:
    """Sum rooms_count for overlapping active bookings on this room."""
    stmt = select(func.coalesce(func.sum(HotelBooking.rooms_count), 0)).where(
        HotelBooking.room_id == room_id,
        HotelBooking.status.in_(COUNTED_STATUSES),
        HotelBooking.check_in < check_out,
        HotelBooking.check_out > check_in,
    )
    if exclude_booking_id is not None:
        stmt = stmt.where(HotelBooking.id != exclude_booking_id)
    if for_update:
        stmt = stmt.with_for_update()
    return int(await db.scalar(stmt) or 0)


async def available_inventory(
    db: AsyncSession,
    *,
    room: HotelRoom,
    check_in: date,
    check_out: date,
    for_update: bool = False,
) -> int:
    booked = await rooms_booked(
        db,
        room_id=room.id,
        check_in=check_in,
        check_out=check_out,
        for_update=for_update,
    )
    return max(0, int(room.inventory_count) - booked)


def compute_total(
    *,
    sale_price: int,
    breakfast_price: int,
    nights: int,
    rooms_count: int,
    breakfast_count: int,
) -> tuple[int, int, int]:
    unit = int(sale_price)
    breakfast_unit = int(breakfast_price)
    total = unit * nights * rooms_count + breakfast_unit * breakfast_count * nights
    return unit, breakfast_unit, total


async def create_hotel_booking(
    db: AsyncSession,
    *,
    room_id: int,
    check_in: date,
    check_out: date,
    rooms_count: int,
    adults: int,
    children: int,
    breakfast_count: int,
    customer_name: str,
    customer_email: str | None,
    customer_phone: str | None,
    payment_method: str,
    total_price: int,
    notes: str | None = None,
    user_id: int | None = None,
) -> HotelBooking:
    if payment_method not in PAYMENT_METHODS:
        raise BookingError("Invalid payment method")
    if rooms_count < 1:
        raise BookingError("At least one room is required")
    if adults < 1:
        raise BookingError("At least one adult is required")
    if children < 0 or breakfast_count < 0:
        raise BookingError("Invalid guest or breakfast count")
    if check_out <= check_in:
        raise BookingError("Check-out must be after check-in")
    if check_in < date.today():
        raise BookingError("Check-in cannot be in the past")

    room = (
        await db.execute(
            select(HotelRoom).where(HotelRoom.id == room_id).with_for_update()
        )
    ).scalar_one_or_none()
    if room is None or not room.is_active:
        raise BookingError("Room not found", status_code=404)

    hotel = await db.get(Hotel, room.hotel_id)
    if hotel is None or not hotel.is_active:
        raise BookingError("Hotel not found", status_code=404)

    nights = (check_out - check_in).days
    available = await available_inventory(
        db,
        room=room,
        check_in=check_in,
        check_out=check_out,
        for_update=True,
    )
    if rooms_count > available:
        raise BookingError(
            f"Only {available} room(s) available for these dates",
            status_code=409,
        )

    unit, breakfast_unit, expected_total = compute_total(
        sale_price=room.sale_price,
        breakfast_price=room.breakfast_price,
        nights=nights,
        rooms_count=rooms_count,
        breakfast_count=breakfast_count,
    )
    if int(total_price) != expected_total:
        raise BookingError(
            f"Price changed. Expected {expected_total}",
            status_code=409,
        )

    booking = HotelBooking(
        booking_code=await _generate_code(db),
        user_id=user_id,
        hotel_id=hotel.id,
        room_id=room.id,
        check_in=check_in,
        check_out=check_out,
        nights=nights,
        rooms_count=rooms_count,
        adults=adults,
        children=children,
        breakfast_count=breakfast_count,
        unit_price=unit,
        breakfast_unit_price=breakfast_unit,
        total_price=expected_total,
        customer_name=customer_name.strip(),
        customer_email=(customer_email or "").strip() or None,
        customer_phone=(customer_phone or "").strip() or None,
        status="pending",
        payment_method=payment_method,
        payment_status="unpaid",
        notes=notes,
        hotel_name_snapshot=hotel.name,
        room_name_snapshot=room.name,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(booking)
    await db.flush()
    await db.refresh(booking)
    return booking
