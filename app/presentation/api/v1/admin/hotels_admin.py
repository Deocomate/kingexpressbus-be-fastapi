"""Admin CRUD: hotels + rooms; hotel booking list/actions."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import func, or_, select

from app.application.catalog.admin_list import paginate, slugify
from app.application.catalog.reorder import reorder_full_table
from app.application.hotel import update_hotel_booking_status
from app.application.hotel.shared import BookingError
from app.core.deps import AppSettings, DbSession
from app.infrastructure.mail import service_mail
from app.infrastructure.persistence.models import Hotel, HotelBooking, HotelRoom
from app.infrastructure.persistence.session import AsyncSessionLocal
from app.presentation.api.v1.admin.deps import AdminUser, SameOrigin
from app.presentation.schemas.admin_common import MessageOut, Paginated, ReorderRequest
from app.presentation.schemas.hotel import (
    HotelBookingActionOut,
    HotelBookingCancelIn,
    HotelBookingOut,
    HotelOut,
    HotelRoomOut,
    HotelRoomWrite,
    HotelWrite,
)

router = APIRouter(prefix="/admin", tags=["admin-hotels"])


async def _bg_mail(
    booking_id: int, kind: str, settings: AppSettings, cancel_reason: str | None = None
) -> None:
    async with AsyncSessionLocal() as session:
        await service_mail.queue_service_booking_mail(
            session,
            service_kind="hotel",
            booking_id=booking_id,
            kind=kind,
            settings=settings,
            cancel_reason=cancel_reason,
        )


def _hotel_out(hotel: Hotel) -> HotelOut:
    rooms = [HotelRoomOut.model_validate(r) for r in (hotel.rooms or [])]
    data = HotelOut.model_validate(hotel)
    data.rooms = rooms
    return data


# ── Hotels ─────────────────────────────────────────────────────────────────
@router.get("/hotels", response_model=Paginated[HotelOut])
async def list_hotels(
    db: DbSession,
    _: AdminUser,
    page: int = 1,
    page_size: int = 25,
    q: str | None = None,
) -> Paginated[HotelOut]:
    stmt = select(Hotel).order_by(Hotel.priority.desc(), Hotel.name.asc())
    if q:
        stmt = stmt.where(
            or_(Hotel.name.like(f"%{q}%"), Hotel.slug.like(f"%{q}%"), Hotel.address.like(f"%{q}%"))
        )
    items, total = await paginate(db, stmt, page=page, page_size=page_size)
    return Paginated(
        items=[_hotel_out(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/hotels", response_model=HotelOut, status_code=201)
async def create_hotel(
    body: HotelWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> HotelOut:
    max_p = int(await db.scalar(select(func.coalesce(func.max(Hotel.priority), 0))) or 0)
    slug = (body.slug or slugify(body.name)).strip()
    row = Hotel(
        name=body.name,
        slug=slug,
        address=body.address,
        short_description=body.short_description,
        description=body.description,
        amenities=body.amenities,
        policies=body.policies,
        thumbnail_url=body.thumbnail_url,
        image_list_url=body.image_list_url,
        map_embedded=body.map_embedded,
        check_in_from=body.check_in_from,
        check_in_to=body.check_in_to,
        check_out_from=body.check_out_from,
        check_out_to=body.check_out_to,
        rating_score=body.rating_score,
        rating_label=body.rating_label,
        rating_count=body.rating_count,
        is_active=body.is_active,
        priority=body.priority if body.priority is not None else max_p + 1,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _hotel_out(row)


@router.put("/hotels/{hotel_id}", response_model=HotelOut)
async def update_hotel(
    hotel_id: int, body: HotelWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> HotelOut:
    row = await db.get(Hotel, hotel_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    data = body.model_dump()
    if not data.get("slug"):
        data["slug"] = slugify(body.name)
    for key, value in data.items():
        if key == "priority" and value is None:
            continue
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return _hotel_out(row)


@router.delete("/hotels/{hotel_id}", response_model=MessageOut)
async def delete_hotel(
    hotel_id: int, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    row = await db.get(Hotel, hotel_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    await db.delete(row)
    await db.commit()
    return MessageOut(message="Deleted")


@router.post("/hotels/reorder", response_model=MessageOut)
async def reorder_hotels(
    body: ReorderRequest, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    await reorder_full_table(db, Hotel, body.ids)
    await db.commit()
    return MessageOut(message="Reordered")


# ── Rooms ──────────────────────────────────────────────────────────────────
@router.get("/hotels/{hotel_id}/rooms", response_model=Paginated[HotelRoomOut])
async def list_rooms(
    hotel_id: int,
    db: DbSession,
    _: AdminUser,
    page: int = 1,
    page_size: int = 50,
) -> Paginated[HotelRoomOut]:
    stmt = (
        select(HotelRoom)
        .where(HotelRoom.hotel_id == hotel_id)
        .order_by(HotelRoom.priority.desc(), HotelRoom.name.asc())
    )
    items, total = await paginate(db, stmt, page=page, page_size=page_size)
    return Paginated(
        items=[HotelRoomOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/hotels/{hotel_id}/rooms", response_model=HotelRoomOut, status_code=201)
async def create_room(
    hotel_id: int, body: HotelRoomWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> HotelRoom:
    hotel = await db.get(Hotel, hotel_id)
    if hotel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    max_p = int(
        await db.scalar(
            select(func.coalesce(func.max(HotelRoom.priority), 0)).where(
                HotelRoom.hotel_id == hotel_id
            )
        )
        or 0
    )
    row = HotelRoom(
        hotel_id=hotel_id,
        name=body.name,
        slug=(body.slug or slugify(body.name)).strip(),
        capacity_adults=body.capacity_adults,
        bed_label=body.bed_label,
        size_m2=body.size_m2,
        amenities=body.amenities,
        thumbnail_url=body.thumbnail_url,
        image_list_url=body.image_list_url,
        base_price=body.base_price,
        sale_price=body.sale_price,
        breakfast_price=body.breakfast_price,
        cancel_fee_percent=body.cancel_fee_percent,
        inventory_count=body.inventory_count,
        is_active=body.is_active,
        priority=body.priority if body.priority is not None else max_p + 1,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.put("/hotel-rooms/{room_id}", response_model=HotelRoomOut)
async def update_room(
    room_id: int, body: HotelRoomWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> HotelRoom:
    row = await db.get(HotelRoom, room_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Room not found")
    data = body.model_dump()
    if not data.get("slug"):
        data["slug"] = slugify(body.name)
    for key, value in data.items():
        if key == "priority" and value is None:
            continue
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/hotel-rooms/{room_id}", response_model=MessageOut)
async def delete_room(
    room_id: int, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    row = await db.get(HotelRoom, room_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Room not found")
    await db.delete(row)
    await db.commit()
    return MessageOut(message="Deleted")


# ── Hotel bookings ─────────────────────────────────────────────────────────
@router.get("/hotel-bookings", response_model=Paginated[HotelBookingOut])
async def list_hotel_bookings(
    db: DbSession,
    _: AdminUser,
    page: int = 1,
    page_size: int = 25,
    q: str | None = None,
    status_filter: str | None = None,
) -> Paginated[HotelBookingOut]:
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
    items, total = await paginate(db, stmt, page=page, page_size=page_size)
    return Paginated(
        items=[HotelBookingOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/hotel-bookings/{booking_id}", response_model=HotelBookingOut)
async def get_hotel_booking(
    booking_id: int, db: DbSession, _: AdminUser
) -> HotelBooking:
    row = await db.get(HotelBooking, booking_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return row


@router.post("/hotel-bookings/{booking_id}/confirm", response_model=HotelBookingActionOut)
async def confirm_hotel_booking(
    booking_id: int,
    background_tasks: BackgroundTasks,
    db: DbSession,
    settings: AppSettings,
    _: AdminUser,
    __: SameOrigin,
) -> HotelBookingActionOut:
    booking = await db.get(HotelBooking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.status != "pending":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only pending bookings can be confirmed",
        )
    try:
        result = await update_hotel_booking_status(db, booking_id, "confirmed")
        await db.commit()
        await db.refresh(result.booking)
    except BookingError as exc:
        await db.rollback()
        raise HTTPException(exc.status_code, detail=exc.message) from exc
    if result.email_action:
        background_tasks.add_task(_bg_mail, booking_id, result.email_action, settings)
    return HotelBookingActionOut(
        success=True,
        message="Booking confirmed",
        booking=HotelBookingOut.model_validate(result.booking),
    )


@router.post("/hotel-bookings/{booking_id}/complete", response_model=HotelBookingActionOut)
async def complete_hotel_booking(
    booking_id: int, db: DbSession, _: AdminUser, __: SameOrigin
) -> HotelBookingActionOut:
    booking = await db.get(HotelBooking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.status != "confirmed":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only confirmed bookings can be completed",
        )
    try:
        result = await update_hotel_booking_status(db, booking_id, "completed")
        await db.commit()
        await db.refresh(result.booking)
    except BookingError as exc:
        await db.rollback()
        raise HTTPException(exc.status_code, detail=exc.message) from exc
    return HotelBookingActionOut(
        success=True,
        message="Booking completed",
        booking=HotelBookingOut.model_validate(result.booking),
    )


@router.post("/hotel-bookings/{booking_id}/cancel", response_model=HotelBookingActionOut)
async def cancel_hotel_booking(
    booking_id: int,
    body: HotelBookingCancelIn,
    background_tasks: BackgroundTasks,
    db: DbSession,
    settings: AppSettings,
    _: AdminUser,
    __: SameOrigin,
) -> HotelBookingActionOut:
    booking = await db.get(HotelBooking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.status == "cancelled":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Already cancelled"
        )
    try:
        result = await update_hotel_booking_status(
            db, booking_id, "cancelled", notes_text=body.reason
        )
        await db.commit()
        await db.refresh(result.booking)
    except BookingError as exc:
        await db.rollback()
        raise HTTPException(exc.status_code, detail=exc.message) from exc
    if result.email_action:
        background_tasks.add_task(
            _bg_mail, booking_id, result.email_action, settings, body.reason
        )
    return HotelBookingActionOut(
        success=True,
        message="Booking cancelled",
        booking=HotelBookingOut.model_validate(result.booking),
    )
