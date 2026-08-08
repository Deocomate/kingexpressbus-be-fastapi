"""Admin hotel + room CRUD and hotel-booking queries (application layer)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.catalog.admin_list import paginate, slugify
from app.application.catalog.reorder import reorder_full_table
from app.domain.shared.errors import NotFoundError
from app.infrastructure.persistence.models import Hotel, HotelBooking, HotelRoom


async def list_hotels(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 25,
    q: str | None = None,
) -> tuple[list[Hotel], int]:
    stmt = select(Hotel).order_by(Hotel.priority.desc(), Hotel.name.asc())
    if q:
        stmt = stmt.where(
            or_(Hotel.name.like(f"%{q}%"), Hotel.slug.like(f"%{q}%"), Hotel.address.like(f"%{q}%"))
        )
    return await paginate(db, stmt, page=page, page_size=page_size)


async def create_hotel(db: AsyncSession, data: dict[str, Any]) -> Hotel:
    max_p = int(await db.scalar(select(func.coalesce(func.max(Hotel.priority), 0))) or 0)
    slug = (data.get("slug") or slugify(data["name"])).strip()
    priority = data.get("priority")
    row = Hotel(
        name=data["name"],
        slug=slug,
        address=data.get("address"),
        short_description=data.get("short_description"),
        description=data.get("description"),
        amenities=data.get("amenities"),
        policies=data.get("policies"),
        thumbnail_url=data.get("thumbnail_url"),
        image_list_url=data.get("image_list_url"),
        map_embedded=data.get("map_embedded"),
        check_in_from=data.get("check_in_from"),
        check_in_to=data.get("check_in_to"),
        check_out_from=data.get("check_out_from"),
        check_out_to=data.get("check_out_to"),
        rating_score=data.get("rating_score"),
        rating_label=data.get("rating_label"),
        rating_count=data.get("rating_count") or 0,
        is_active=bool(data.get("is_active", True)),
        priority=priority if priority is not None else max_p + 1,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def update_hotel(db: AsyncSession, hotel_id: int, data: dict[str, Any]) -> Hotel:
    row = await db.get(Hotel, hotel_id)
    if row is None:
        raise NotFoundError("Hotel not found")
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


async def delete_hotel(db: AsyncSession, hotel_id: int) -> None:
    row = await db.get(Hotel, hotel_id)
    if row is None:
        raise NotFoundError("Hotel not found")
    await db.delete(row)
    await db.flush()


async def reorder_hotels(db: AsyncSession, ids: list[int]) -> None:
    await reorder_full_table(db, Hotel, ids)


async def list_rooms(
    db: AsyncSession,
    *,
    hotel_id: int,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[HotelRoom], int]:
    stmt = (
        select(HotelRoom)
        .where(HotelRoom.hotel_id == hotel_id)
        .order_by(HotelRoom.priority.desc(), HotelRoom.name.asc())
    )
    return await paginate(db, stmt, page=page, page_size=page_size)


async def create_room(
    db: AsyncSession, *, hotel_id: int, data: dict[str, Any]
) -> HotelRoom:
    hotel = await db.get(Hotel, hotel_id)
    if hotel is None:
        raise NotFoundError("Hotel not found")
    max_p = int(
        await db.scalar(
            select(func.coalesce(func.max(HotelRoom.priority), 0)).where(
                HotelRoom.hotel_id == hotel_id
            )
        )
        or 0
    )
    priority = data.get("priority")
    row = HotelRoom(
        hotel_id=hotel_id,
        name=data["name"],
        slug=(data.get("slug") or slugify(data["name"])).strip(),
        capacity_adults=data.get("capacity_adults", 1),
        bed_label=data.get("bed_label"),
        size_m2=data.get("size_m2"),
        amenities=data.get("amenities"),
        thumbnail_url=data.get("thumbnail_url"),
        image_list_url=data.get("image_list_url"),
        base_price=data["base_price"],
        sale_price=data["sale_price"],
        breakfast_price=data.get("breakfast_price", 0),
        cancel_fee_percent=data.get("cancel_fee_percent", 0),
        inventory_count=data.get("inventory_count", 1),
        is_active=bool(data.get("is_active", True)),
        priority=priority if priority is not None else max_p + 1,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def update_room(db: AsyncSession, room_id: int, data: dict[str, Any]) -> HotelRoom:
    row = await db.get(HotelRoom, room_id)
    if row is None:
        raise NotFoundError("Room not found")
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


async def delete_room(db: AsyncSession, room_id: int) -> None:
    row = await db.get(HotelRoom, room_id)
    if row is None:
        raise NotFoundError("Room not found")
    await db.delete(row)
    await db.flush()


async def list_hotel_bookings(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 25,
    q: str | None = None,
    status_filter: str | None = None,
) -> tuple[list[HotelBooking], int]:
    stmt = select(HotelBooking).order_by(HotelBooking.id.desc())
    if status_filter:
        stmt = stmt.where(HotelBooking.status == status_filter)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                HotelBooking.booking_code.like(like),
                HotelBooking.customer_name.like(like),
                HotelBooking.customer_email.like(like),
                HotelBooking.customer_phone.like(like),
            )
        )
    return await paginate(db, stmt, page=page, page_size=page_size)


async def get_hotel_booking(db: AsyncSession, booking_id: int) -> HotelBooking:
    row = await db.get(HotelBooking, booking_id)
    if row is None:
        raise NotFoundError("Booking not found")
    return row
