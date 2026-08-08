"""Admin booking create (manual/phone) + field edit."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.application.booking import booking_creation, booking_edit
from app.application.booking.booking_shared import BookingError, PriceChangedError
from app.core.deps import AppSettings, DbSession
from app.presentation.api.v1.admin.bookings._shared import bg_mail, booking_out
from app.presentation.api.v1.admin.deps import AdminUser, SameOrigin
from app.presentation.schemas.booking import (
    BookingAdminUpdateIn,
    BookingCreateIn,
    BookingOut,
)

router = APIRouter(prefix="/admin/bookings", tags=["admin-bookings"])


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def admin_create_booking(
    body: BookingCreateIn,
    background_tasks: BackgroundTasks,
    db: DbSession,
    settings: AppSettings,
    _admin: AdminUser,
    _origin: SameOrigin,
) -> BookingOut:
    """Manual booking create for ops taking a booking by phone.

    Reuses the exact same server-authoritative pricing path as the public
    client funnel (app/api/v1/bookings/booking_routes.py create_booking) —
    no separate admin pricing logic to keep in sync.
    """
    try:
        booking = await booking_creation.create_booking(
            db,
            trip_id=body.trip_id,
            booking_date=body.booking_date,
            quantity=body.quantity,
            customer_name=body.customer_name,
            customer_phone=body.customer_phone,
            customer_email=str(body.customer_email),
            dropoff_stop_id=body.dropoff_stop_id,
            total_price=body.total_price,
            payment_method=body.payment_method,
            pickup_stop_id=body.pickup_stop_id,
            is_hotel_pickup=body.is_hotel_pickup,
            hotel_pickup_address=body.hotel_pickup_address,
            notes_text=body.notes,
        )
        await db.commit()
        await db.refresh(booking)
    except PriceChangedError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"message": "price_changed", "server_total": exc.server_total},
        ) from exc
    except BookingError as exc:
        await db.rollback()
        raise HTTPException(exc.status_code, detail=exc.message) from exc

    background_tasks.add_task(bg_mail, booking.id, "confirmation", settings)
    return booking_out(booking)


@router.put("/{booking_id}", response_model=BookingOut)
async def admin_update_booking(
    booking_id: int,
    body: BookingAdminUpdateIn,
    db: DbSession,
    _admin: AdminUser,
    _origin: SameOrigin,
) -> BookingOut:
    try:
        booking = await booking_edit.update_booking_fields(
            db,
            booking_id,
            customer_name=body.customer_name,
            customer_phone=body.customer_phone,
            customer_email=str(body.customer_email) if body.customer_email else None,
            pickup_stop_id=body.pickup_stop_id,
            dropoff_stop_id=body.dropoff_stop_id,
            quantity=body.quantity,
            notes_text=body.notes,
            hotel_pickup_address=body.hotel_pickup_address,
        )
        await db.commit()
        await db.refresh(booking)
    except BookingError as exc:
        await db.rollback()
        raise HTTPException(exc.status_code, detail=exc.message) from exc
    return booking_out(booking)
