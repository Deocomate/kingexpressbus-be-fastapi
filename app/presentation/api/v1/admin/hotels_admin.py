"""Admin HTTP adapters: hotels + rooms + hotel booking actions."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.application.hotel import admin_crud, update_hotel_booking_status
from app.application.hotel.shared import BookingError
from app.core.deps import AppSettings, DbSession
from app.domain.shared.errors import NotFoundError
from app.infrastructure.mail import service_mail
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


def _hotel_out(hotel) -> HotelOut:
    rooms = [HotelRoomOut.model_validate(r) for r in (hotel.rooms or [])]
    data = HotelOut.model_validate(hotel)
    data.rooms = rooms
    return data


def _map_not_found(exc: NotFoundError) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=exc.message)


@router.get("/hotels", response_model=Paginated[HotelOut])
async def list_hotels(
    db: DbSession,
    _: AdminUser,
    page: int = 1,
    page_size: int = 25,
    q: str | None = None,
) -> Paginated[HotelOut]:
    items, total = await admin_crud.list_hotels(db, page=page, page_size=page_size, q=q)
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
    row = await admin_crud.create_hotel(db, body.model_dump())
    await db.commit()
    await db.refresh(row)
    return _hotel_out(row)


@router.put("/hotels/{hotel_id}", response_model=HotelOut)
async def update_hotel(
    hotel_id: int, body: HotelWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> HotelOut:
    try:
        row = await admin_crud.update_hotel(db, hotel_id, body.model_dump())
        await db.commit()
        await db.refresh(row)
    except NotFoundError as exc:
        await db.rollback()
        raise _map_not_found(exc) from exc
    return _hotel_out(row)


@router.delete("/hotels/{hotel_id}", response_model=MessageOut)
async def delete_hotel(
    hotel_id: int, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    try:
        await admin_crud.delete_hotel(db, hotel_id)
        await db.commit()
    except NotFoundError as exc:
        await db.rollback()
        raise _map_not_found(exc) from exc
    return MessageOut(message="Deleted")


@router.post("/hotels/reorder", response_model=MessageOut)
async def reorder_hotels(
    body: ReorderRequest, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    await admin_crud.reorder_hotels(db, body.ids)
    await db.commit()
    return MessageOut(message="Reordered")


@router.get("/hotels/{hotel_id}/rooms", response_model=Paginated[HotelRoomOut])
async def list_rooms(
    hotel_id: int,
    db: DbSession,
    _: AdminUser,
    page: int = 1,
    page_size: int = 50,
) -> Paginated[HotelRoomOut]:
    items, total = await admin_crud.list_rooms(
        db, hotel_id=hotel_id, page=page, page_size=page_size
    )
    return Paginated(
        items=[HotelRoomOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/hotels/{hotel_id}/rooms", response_model=HotelRoomOut, status_code=201)
async def create_room(
    hotel_id: int, body: HotelRoomWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> HotelRoomOut:
    try:
        row = await admin_crud.create_room(db, hotel_id=hotel_id, data=body.model_dump())
        await db.commit()
        await db.refresh(row)
    except NotFoundError as exc:
        await db.rollback()
        raise _map_not_found(exc) from exc
    return HotelRoomOut.model_validate(row)


@router.put("/hotel-rooms/{room_id}", response_model=HotelRoomOut)
async def update_room(
    room_id: int, body: HotelRoomWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> HotelRoomOut:
    try:
        row = await admin_crud.update_room(db, room_id, body.model_dump())
        await db.commit()
        await db.refresh(row)
    except NotFoundError as exc:
        await db.rollback()
        raise _map_not_found(exc) from exc
    return HotelRoomOut.model_validate(row)


@router.delete("/hotel-rooms/{room_id}", response_model=MessageOut)
async def delete_room(
    room_id: int, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    try:
        await admin_crud.delete_room(db, room_id)
        await db.commit()
    except NotFoundError as exc:
        await db.rollback()
        raise _map_not_found(exc) from exc
    return MessageOut(message="Deleted")


@router.get("/hotel-bookings", response_model=Paginated[HotelBookingOut])
async def list_hotel_bookings(
    db: DbSession,
    _: AdminUser,
    page: int = 1,
    page_size: int = 25,
    q: str | None = None,
    status_filter: str | None = None,
) -> Paginated[HotelBookingOut]:
    items, total = await admin_crud.list_hotel_bookings(
        db, page=page, page_size=page_size, q=q, status_filter=status_filter
    )
    return Paginated(
        items=[HotelBookingOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/hotel-bookings/{booking_id}", response_model=HotelBookingOut)
async def get_hotel_booking(
    booking_id: int, db: DbSession, _: AdminUser
) -> HotelBookingOut:
    try:
        row = await admin_crud.get_hotel_booking(db, booking_id)
    except NotFoundError as exc:
        raise _map_not_found(exc) from exc
    return HotelBookingOut.model_validate(row)


@router.post("/hotel-bookings/{booking_id}/confirm", response_model=HotelBookingActionOut)
async def confirm_hotel_booking(
    booking_id: int,
    background_tasks: BackgroundTasks,
    db: DbSession,
    settings: AppSettings,
    _: AdminUser,
    __: SameOrigin,
) -> HotelBookingActionOut:
    try:
        booking = await admin_crud.get_hotel_booking(db, booking_id)
    except NotFoundError as exc:
        raise _map_not_found(exc) from exc
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
    try:
        booking = await admin_crud.get_hotel_booking(db, booking_id)
    except NotFoundError as exc:
        raise _map_not_found(exc) from exc
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
    try:
        booking = await admin_crud.get_hotel_booking(db, booking_id)
    except NotFoundError as exc:
        raise _map_not_found(exc) from exc
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
