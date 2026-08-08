"""Public hotel listing + hotel booking create/detail (signed success URL)."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.application.auth import customer_accounts
from app.application.hotel import available_inventory, create_hotel_booking
from app.application.hotel.shared import BookingError
from app.core.deps import AppSettings, DbSession, get_current_user_optional
from app.core.rate_limit import client_ip, rate_limiter
from app.infrastructure.mail import service_mail
from app.infrastructure.persistence.models import Hotel, HotelBooking, HotelRoom, User
from app.infrastructure.persistence.session import AsyncSessionLocal
from app.presentation.api.v1.service_booking_urls import (
    issue_signed_success_url,
    verify_signed_booking_access,
)
from app.presentation.schemas.hotel import (
    HotelBookingCreateIn,
    HotelBookingCreateOut,
    HotelBookingOut,
    HotelListOut,
    HotelOut,
    HotelRoomOut,
)

router = APIRouter(tags=["hotels"])


def _room_out(room: HotelRoom, available: int | None = None) -> HotelRoomOut:
    data = HotelRoomOut.model_validate(room)
    data.available_count = available
    return data


def _hotel_out(hotel: Hotel, rooms: list[HotelRoomOut] | None = None) -> HotelOut:
    data = HotelOut.model_validate(hotel)
    if rooms is not None:
        data.rooms = rooms
    elif hotel.rooms:
        data.rooms = [HotelRoomOut.model_validate(r) for r in hotel.rooms if r.is_active]
    return data


async def _bg_hotel_mail(booking_id: int, kind: str, settings: AppSettings) -> None:
    async with AsyncSessionLocal() as session:
        await service_mail.queue_service_booking_mail(
            session,
            service_kind="hotel",
            booking_id=booking_id,
            kind=kind,
            settings=settings,
        )


@router.get("/hotels", response_model=list[HotelListOut])
async def list_hotels(db: DbSession) -> list[Hotel]:
    result = await db.execute(
        select(Hotel)
        .where(Hotel.is_active.is_(True))
        .order_by(Hotel.priority.desc(), Hotel.name.asc())
    )
    return list(result.scalars().all())


@router.get("/hotels/{slug}", response_model=HotelOut)
async def get_hotel(
    slug: str,
    db: DbSession,
    check_in: date | None = Query(None),
    check_out: date | None = Query(None),
) -> HotelOut:
    result = await db.execute(
        select(Hotel).where(Hotel.slug == slug, Hotel.is_active.is_(True))
    )
    hotel = result.scalar_one_or_none()
    if hotel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    rooms_out: list[HotelRoomOut] = []
    for room in sorted(
        [r for r in (hotel.rooms or []) if r.is_active],
        key=lambda r: (-r.priority, r.name),
    ):
        available = None
        if check_in and check_out and check_out > check_in:
            available = await available_inventory(
                db, room=room, check_in=check_in, check_out=check_out
            )
        rooms_out.append(_room_out(room, available))
    return _hotel_out(hotel, rooms_out)


@router.post(
    "/hotel-bookings",
    response_model=HotelBookingCreateOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_booking(
    body: HotelBookingCreateIn,
    request: Request,
    background_tasks: BackgroundTasks,
    db: DbSession,
    settings: AppSettings,
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> HotelBookingCreateOut:
    rate_limiter.hit(f"hotel-booking:ip:{client_ip(request)}", limit=10)
    try:
        if user is not None:
            booking_user_id = user.id
        else:
            guest = await customer_accounts.ensure_customer_user(
                db,
                name=body.customer_name,
                email=str(body.customer_email),
                phone=body.customer_phone,
            )
            booking_user_id = guest.id

        booking = await create_hotel_booking(
            db,
            room_id=body.room_id,
            check_in=body.check_in,
            check_out=body.check_out,
            rooms_count=body.rooms_count,
            adults=body.adults,
            children=body.children,
            breakfast_count=body.breakfast_count,
            customer_name=body.customer_name,
            customer_email=str(body.customer_email),
            customer_phone=body.customer_phone,
            payment_method=body.payment_method,
            total_price=body.total_price,
            notes=body.notes,
            user_id=booking_user_id,
        )
        await db.commit()
        await db.refresh(booking)
    except BookingError as exc:
        await db.rollback()
        raise HTTPException(exc.status_code, detail=exc.message) from exc

    background_tasks.add_task(_bg_hotel_mail, booking.id, "confirmation", settings)
    success_url = issue_signed_success_url(
        settings,
        booking_id=booking.id,
        path_template=settings.hotel_success_path_template,
    )
    return HotelBookingCreateOut(
        booking=HotelBookingOut.model_validate(booking),
        success_url=success_url,
    )


@router.get("/hotel-bookings/{booking_id}", response_model=HotelBookingOut)
async def get_hotel_booking(
    booking_id: int,
    db: DbSession,
    settings: AppSettings,
    expires: int = Query(..., description="Unix expiry from signed success URL"),
    signature: str = Query(..., description="HMAC signature from signed success URL"),
) -> HotelBooking:
    """Full hotel booking detail — requires valid temporary signature (≈24h)."""
    ok = verify_signed_booking_access(
        settings=settings,
        booking_id=booking_id,
        expires=expires,
        signature=signature,
        path_template=settings.hotel_success_path_template,
    )
    if not ok:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Invalid or expired signature"
        )
    booking = await db.get(HotelBooking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking
