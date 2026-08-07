"""Admin booking status actions: confirm / complete / cancel / generic status patch."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.api.v1.admin.bookings._shared import bg_mail, booking_out
from app.api.v1.admin.deps import AdminUser, SameOrigin
from app.core.deps import AppSettings, DbSession
from app.schemas.booking import BookingActionOut, BookingCancelIn, BookingStatusUpdateIn
from app.services import booking_admin_query as booking_query
from app.services import booking_cancel, booking_status
from app.services.booking_shared import BookingError

router = APIRouter(prefix="/admin/bookings", tags=["admin-bookings"])


@router.post("/{booking_id}/confirm", response_model=BookingActionOut)
async def admin_confirm(
    booking_id: int,
    background_tasks: BackgroundTasks,
    db: DbSession,
    settings: AppSettings,
    _admin: AdminUser,
    _origin: SameOrigin,
) -> BookingActionOut:
    booking = await booking_query.get_booking_by_id(db, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.status != "pending":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only pending bookings can be confirmed",
        )
    try:
        result = await booking_status.update_booking_status(db, booking_id, "confirmed")
        await db.commit()
        await db.refresh(result.booking)
    except BookingError as exc:
        await db.rollback()
        raise HTTPException(exc.status_code, detail=exc.message) from exc

    if result.email_action:
        background_tasks.add_task(bg_mail, booking_id, result.email_action, settings)
    return BookingActionOut(
        success=True,
        message="Booking confirmed",
        booking=booking_out(result.booking),
    )


@router.post("/{booking_id}/complete", response_model=BookingActionOut)
async def admin_complete(
    booking_id: int,
    db: DbSession,
    _admin: AdminUser,
    _origin: SameOrigin,
) -> BookingActionOut:
    booking = await booking_query.get_booking_by_id(db, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.status != "confirmed":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only confirmed bookings can be completed",
        )
    try:
        result = await booking_status.update_booking_status(db, booking_id, "completed")
        await db.commit()
        await db.refresh(result.booking)
    except BookingError as exc:
        await db.rollback()
        raise HTTPException(exc.status_code, detail=exc.message) from exc
    return BookingActionOut(
        success=True,
        message="Booking completed",
        booking=booking_out(result.booking),
    )


@router.post("/{booking_id}/cancel", response_model=BookingActionOut)
async def admin_cancel(
    booking_id: int,
    body: BookingCancelIn,
    background_tasks: BackgroundTasks,
    db: DbSession,
    settings: AppSettings,
    admin: AdminUser,
    _origin: SameOrigin,
) -> BookingActionOut:
    booking = await booking_query.get_booking_by_id(db, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.status in ("cancelled", "completed"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot cancel a completed or already cancelled booking",
        )
    try:
        result = await booking_cancel.cancel_booking(
            db,
            booking_id,
            reason=body.reason,
            admin_user_id=admin.id,
        )
        await db.commit()
        await db.refresh(result.booking)
    except BookingError as exc:
        await db.rollback()
        raise HTTPException(exc.status_code, detail=exc.message) from exc

    background_tasks.add_task(
        bg_mail, booking_id, "cancellation", settings, body.reason
    )
    return BookingActionOut(
        success=True,
        message="Booking cancelled",
        booking=booking_out(result.booking),
    )


@router.patch("/{booking_id}/status", response_model=BookingActionOut)
async def admin_update_status(
    booking_id: int,
    body: BookingStatusUpdateIn,
    background_tasks: BackgroundTasks,
    db: DbSession,
    settings: AppSettings,
    _admin: AdminUser,
    _origin: SameOrigin,
) -> BookingActionOut:
    try:
        result = await booking_status.update_booking_status(
            db, booking_id, body.status, notes_text=body.notes
        )
        await db.commit()
        await db.refresh(result.booking)
    except BookingError as exc:
        await db.rollback()
        raise HTTPException(exc.status_code, detail=exc.message) from exc

    if result.email_action:
        background_tasks.add_task(
            bg_mail,
            booking_id,
            result.email_action,
            settings,
            result.cancel_reason,
        )
    return BookingActionOut(
        success=True,
        message="Status updated",
        booking=booking_out(result.booking),
    )
