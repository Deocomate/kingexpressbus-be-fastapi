"""Admin CRUD: tours + tour booking list/actions."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import func, or_, select

from app.application.catalog.admin_list import paginate, slugify
from app.application.catalog.reorder import reorder_full_table
from app.application.hotel.shared import BookingError
from app.application.tour import update_tour_booking_status
from app.core.deps import AppSettings, DbSession
from app.infrastructure.mail import service_mail
from app.infrastructure.persistence.models import Tour, TourBooking
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


@router.get("/tours", response_model=Paginated[TourOut])
async def list_tours(
    db: DbSession,
    _: AdminUser,
    page: int = 1,
    page_size: int = 25,
    q: str | None = None,
) -> Paginated[TourOut]:
    stmt = select(Tour).order_by(Tour.priority.desc(), Tour.name.asc())
    if q:
        stmt = stmt.where(or_(Tour.name.like(f"%{q}%"), Tour.slug.like(f"%{q}%")))
    items, total = await paginate(db, stmt, page=page, page_size=page_size)
    return Paginated(
        items=[TourOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/tours", response_model=TourOut, status_code=201)
async def create_tour(
    body: TourWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> Tour:
    max_p = int(await db.scalar(select(func.coalesce(func.max(Tour.priority), 0))) or 0)
    row = Tour(
        name=body.name,
        slug=(body.slug or slugify(body.name)).strip(),
        short_description=body.short_description,
        description=body.description,
        itinerary=body.itinerary,
        duration_label=body.duration_label,
        duration_hours=body.duration_hours,
        base_price=body.base_price,
        max_guests=body.max_guests,
        highlights=body.highlights,
        includes=body.includes,
        excludes=body.excludes,
        thumbnail_url=body.thumbnail_url,
        image_list_url=body.image_list_url,
        is_active=body.is_active,
        priority=body.priority if body.priority is not None else max_p + 1,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.put("/tours/{tour_id}", response_model=TourOut)
async def update_tour(
    tour_id: int, body: TourWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> Tour:
    row = await db.get(Tour, tour_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tour not found")
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


@router.delete("/tours/{tour_id}", response_model=MessageOut)
async def delete_tour(
    tour_id: int, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    row = await db.get(Tour, tour_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tour not found")
    await db.delete(row)
    await db.commit()
    return MessageOut(message="Deleted")


@router.post("/tours/reorder", response_model=MessageOut)
async def reorder_tours(
    body: ReorderRequest, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    await reorder_full_table(db, Tour, body.ids)
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
    items, total = await paginate(db, stmt, page=page, page_size=page_size)
    return Paginated(
        items=[TourBookingOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/tour-bookings/{booking_id}", response_model=TourBookingOut)
async def get_tour_booking(
    booking_id: int, db: DbSession, _: AdminUser
) -> TourBooking:
    row = await db.get(TourBooking, booking_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return row


@router.post("/tour-bookings/{booking_id}/confirm", response_model=TourBookingActionOut)
async def confirm_tour_booking(
    booking_id: int,
    background_tasks: BackgroundTasks,
    db: DbSession,
    settings: AppSettings,
    _: AdminUser,
    __: SameOrigin,
) -> TourBookingActionOut:
    booking = await db.get(TourBooking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
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
    booking = await db.get(TourBooking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
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
    booking = await db.get(TourBooking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
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
