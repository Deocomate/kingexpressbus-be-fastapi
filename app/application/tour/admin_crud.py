"""Admin tour CRUD and tour-booking queries (application layer)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.catalog.admin_list import paginate, slugify
from app.application.catalog.reorder import reorder_full_table
from app.domain.shared.errors import NotFoundError
from app.infrastructure.persistence.models import Tour, TourBooking


async def list_tours(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 25,
    q: str | None = None,
) -> tuple[list[Tour], int]:
    stmt = select(Tour).order_by(Tour.priority.desc(), Tour.name.asc())
    if q:
        stmt = stmt.where(or_(Tour.name.like(f"%{q}%"), Tour.slug.like(f"%{q}%")))
    return await paginate(db, stmt, page=page, page_size=page_size)


async def create_tour(db: AsyncSession, data: dict[str, Any]) -> Tour:
    max_p = int(await db.scalar(select(func.coalesce(func.max(Tour.priority), 0))) or 0)
    priority = data.get("priority")
    row = Tour(
        name=data["name"],
        slug=(data.get("slug") or slugify(data["name"])).strip(),
        short_description=data.get("short_description"),
        description=data.get("description"),
        itinerary=data.get("itinerary"),
        duration_label=data.get("duration_label"),
        duration_hours=data.get("duration_hours"),
        base_price=data["base_price"],
        max_guests=data.get("max_guests", 1),
        highlights=data.get("highlights"),
        includes=data.get("includes"),
        excludes=data.get("excludes"),
        thumbnail_url=data.get("thumbnail_url"),
        image_list_url=data.get("image_list_url"),
        is_active=bool(data.get("is_active", True)),
        priority=priority if priority is not None else max_p + 1,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def update_tour(db: AsyncSession, tour_id: int, data: dict[str, Any]) -> Tour:
    row = await db.get(Tour, tour_id)
    if row is None:
        raise NotFoundError("Tour not found")
    payload = dict(data)
    if not payload.get("slug"):
        payload["slug"] = slugify(payload["name"])
    for key, value in payload.items():
        if key == "priority" and value is None:
            continue
        setattr(row, key, value)
    await db.flush()
    await db.refresh(row)
    return row


async def delete_tour(db: AsyncSession, tour_id: int) -> None:
    row = await db.get(Tour, tour_id)
    if row is None:
        raise NotFoundError("Tour not found")
    await db.delete(row)
    await db.flush()


async def reorder_tours(db: AsyncSession, ids: list[int]) -> None:
    await reorder_full_table(db, Tour, ids)


async def list_tour_bookings(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 25,
    q: str | None = None,
    status_filter: str | None = None,
) -> tuple[list[TourBooking], int]:
    stmt = select(TourBooking).order_by(TourBooking.id.desc())
    if status_filter:
        stmt = stmt.where(TourBooking.status == status_filter)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                TourBooking.booking_code.like(like),
                TourBooking.customer_name.like(like),
                TourBooking.customer_email.like(like),
                TourBooking.customer_phone.like(like),
            )
        )
    return await paginate(db, stmt, page=page, page_size=page_size)


async def get_tour_booking(db: AsyncSession, booking_id: int) -> TourBooking:
    row = await db.get(TourBooking, booking_id)
    if row is None:
        raise NotFoundError("Booking not found")
    return row
