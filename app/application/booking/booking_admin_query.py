"""Booking lookups + admin list/count/filter helpers."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.booking.booking_shared import ALL_STATUSES
from app.infrastructure.persistence.models import Booking, Trip


async def get_booking_by_code(db: AsyncSession, code: str) -> Booking | None:
    result = await db.execute(select(Booking).where(Booking.booking_code == code))
    return result.scalar_one_or_none()


async def get_booking_by_id(db: AsyncSession, booking_id: int) -> Booking | None:
    return await db.get(Booking, booking_id)


async def list_bookings_for_user(db: AsyncSession, user_id: int) -> list[Booking]:
    result = await db.execute(
        select(Booking)
        .where(Booking.user_id == user_id)
        .order_by(Booking.booking_date.desc(), Booking.id.desc())
    )
    return list(result.scalars().all())


async def list_bookings_admin(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 25,
    status_filter: str | None = None,
    q: str | None = None,
    upcoming: bool = False,
) -> tuple[list[Booking], int]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    stmt = select(Booking)
    if upcoming:
        # Upcoming filter:
        # pending/confirmed bookings ordered by departure (date, then trip
        # start time). status/q filters are ignored in this mode, same as
        # the admin dashboard upcoming list.
        stmt = (
            stmt.join(Trip, Booking.trip_id == Trip.id)
            .where(Booking.status.in_(("pending", "confirmed")))
            .where(Booking.booking_date >= date.today())
            .order_by(Booking.booking_date.asc(), Trip.start_time.asc())
        )
    else:
        if status_filter and status_filter in ALL_STATUSES:
            stmt = stmt.where(Booking.status == status_filter)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                (Booking.booking_code.like(like))
                | (Booking.customer_name.like(like))
                | (Booking.customer_phone.like(like))
            )
        # Newest booking requests first (created_at), not departure date.
        stmt = stmt.order_by(Booking.created_at.desc(), Booking.id.desc())
    total = int(
        await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    )
    result = await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    return list(result.scalars().all()), total


async def count_bookings_by_status(db: AsyncSession) -> dict[str, int]:
    rows = (await db.execute(select(Booking.status, func.count()).group_by(Booking.status))).all()
    counts = {status_val: 0 for status_val in ALL_STATUSES}
    for status_val, count in rows:
        counts[str(status_val)] = int(count)
    counts["all"] = sum(counts.values())
    return counts
