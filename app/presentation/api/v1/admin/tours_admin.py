"""Admin HTTP adapters: tours + tour booking actions."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.application.hotel.shared import BookingError
from app.application.tour import admin_crud, update_tour_booking_status
from app.core.deps import AppSettings, DbSession
from app.domain.shared.errors import NotFoundError
from app.infrastructure.mail import service_mail
from app.infrastructure.persistence.session import AsyncSessionLocal
from app.presentation.api.v1.admin.deps import AdminUser, SameOrigin
from app.presentation.schemas.admin_common import MessageOut, Paginated, ReorderRequest
from app.presentation.schemas.tour import (
    TourBookingActionOut,
    TourBookingCancelIn,
    TourBookingOut,
    TourOut,
    TourWrite,
)

router = APIRouter(prefix="/admin", tags=["admin-tours"])


async def _bg_mail(
    booking_id: int, kind: str, settings: AppSettings, cancel_reason: str | None = None
) -> None:
    async with AsyncSessionLocal() as session:
        await service_mail.queue_service_booking_mail(
            session,
            service_kind="tour",
            booking_id=booking_id,
            kind=kind,
            settings=settings,
            cancel_reason=cancel_reason,
        )


def _map_not_found(exc: NotFoundError) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=exc.message)


@router.get("/tours", response_model=Paginated[TourOut])
async def list_tours(
    db: DbSession,
    _: AdminUser,
    page: int = 1,
    page_size: int = 25,
    q: str | None = None,
) -> Paginated[TourOut]:
    items, total = await admin_crud.list_tours(db, page=page, page_size=page_size, q=q)
    return Paginated(
        items=[TourOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/tours", response_model=TourOut, status_code=201)
async def create_tour(
    body: TourWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> TourOut:
    row = await admin_crud.create_tour(db, body.model_dump())
    await db.commit()
    await db.refresh(row)
    return TourOut.model_validate(row)


@router.put("/tours/{tour_id}", response_model=TourOut)
async def update_tour(
    tour_id: int, body: TourWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> TourOut:
    try:
        row = await admin_crud.update_tour(db, tour_id, body.model_dump())
        await db.commit()
        await db.refresh(row)
    except NotFoundError as exc:
        await db.rollback()
        raise _map_not_found(exc) from exc
    return TourOut.model_validate(row)


@router.delete("/tours/{tour_id}", response_model=MessageOut)
async def delete_tour(
    tour_id: int, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    try:
        await admin_crud.delete_tour(db, tour_id)
        await db.commit()
    except NotFoundError as exc:
        await db.rollback()
        raise _map_not_found(exc) from exc
    return MessageOut(message="Deleted")


@router.post("/tours/reorder", response_model=MessageOut)
async def reorder_tours(
    body: ReorderRequest, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    await admin_crud.reorder_tours(db, body.ids)
    await db.commit()
    return MessageOut(message="Reordered")


@router.get("/tour-bookings", response_model=Paginated[TourBookingOut])
async def list_tour_bookings(
    db: DbSession,
    _: AdminUser,
    page: int = 1,
    page_size: int = 25,
    q: str | None = None,
    status_filter: str | None = None,
) -> Paginated[TourBookingOut]:
    items, total = await admin_crud.list_tour_bookings(
        db, page=page, page_size=page_size, q=q, status_filter=status_filter
    )
    return Paginated(
        items=[TourBookingOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/tour-bookings/{booking_id}", response_model=TourBookingOut)
async def get_tour_booking(
    booking_id: int, db: DbSession, _: AdminUser
) -> TourBookingOut:
    try:
        row = await admin_crud.get_tour_booking(db, booking_id)
    except NotFoundError as exc:
        raise _map_not_found(exc) from exc
    return TourBookingOut.model_validate(row)


@router.post("/tour-bookings/{booking_id}/confirm", response_model=TourBookingActionOut)
async def confirm_tour_booking(
    booking_id: int,
    background_tasks: BackgroundTasks,
    db: DbSession,
    settings: AppSettings,
    _: AdminUser,
    __: SameOrigin,
) -> TourBookingActionOut:
    try:
        booking = await admin_crud.get_tour_booking(db, booking_id)
    except NotFoundError as exc:
        raise _map_not_found(exc) from exc
    if booking.status != "pending":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only pending bookings can be confirmed",
        )
    try:
        result = await update_tour_booking_status(db, booking_id, "confirmed")
        await db.commit()
        await db.refresh(result.booking)
    except BookingError as exc:
        await db.rollback()
        raise HTTPException(exc.status_code, detail=exc.message) from exc
    if result.email_action:
        background_tasks.add_task(_bg_mail, booking_id, result.email_action, settings)
    return TourBookingActionOut(
        success=True,
        message="Booking confirmed",
        booking=TourBookingOut.model_validate(result.booking),
    )


@router.post("/tour-bookings/{booking_id}/complete", response_model=TourBookingActionOut)
async def complete_tour_booking(
    booking_id: int, db: DbSession, _: AdminUser, __: SameOrigin
) -> TourBookingActionOut:
    try:
        booking = await admin_crud.get_tour_booking(db, booking_id)
    except NotFoundError as exc:
        raise _map_not_found(exc) from exc
    if booking.status != "confirmed":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only confirmed bookings can be completed",
        )
    try:
        result = await update_tour_booking_status(db, booking_id, "completed")
        await db.commit()
        await db.refresh(result.booking)
    except BookingError as exc:
        await db.rollback()
        raise HTTPException(exc.status_code, detail=exc.message) from exc
    return TourBookingActionOut(
        success=True,
        message="Booking completed",
        booking=TourBookingOut.model_validate(result.booking),
    )


@router.post("/tour-bookings/{booking_id}/cancel", response_model=TourBookingActionOut)
async def cancel_tour_booking(
    booking_id: int,
    body: TourBookingCancelIn,
    background_tasks: BackgroundTasks,
    db: DbSession,
    settings: AppSettings,
    _: AdminUser,
    __: SameOrigin,
) -> TourBookingActionOut:
    try:
        booking = await admin_crud.get_tour_booking(db, booking_id)
    except NotFoundError as exc:
        raise _map_not_found(exc) from exc
    if booking.status == "cancelled":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Already cancelled"
        )
    try:
        result = await update_tour_booking_status(
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
    return TourBookingActionOut(
        success=True,
        message="Booking cancelled",
        booking=TourBookingOut.model_validate(result.booking),
    )
