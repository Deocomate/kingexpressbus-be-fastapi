"""Public tour listing + tour booking create/detail (signed success URL)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.application.auth import customer_accounts
from app.application.hotel.shared import BookingError
from app.application.tour import create_tour_booking
from app.core.deps import AppSettings, DbSession, get_current_user_optional
from app.core.rate_limit import client_ip, rate_limiter
from app.infrastructure.mail import service_mail
from app.infrastructure.persistence.models import Tour, TourBooking, User
from app.infrastructure.persistence.session import AsyncSessionLocal
from app.presentation.api.v1.service_booking_urls import (
    issue_signed_success_url,
    verify_signed_booking_access,
)
from app.presentation.schemas.tour import (
    TourBookingCreateIn,
    TourBookingCreateOut,
    TourBookingOut,
    TourListOut,
    TourOut,
)

router = APIRouter(tags=["tours"])


async def _bg_tour_mail(booking_id: int, kind: str, settings: AppSettings) -> None:
    async with AsyncSessionLocal() as session:
        await service_mail.queue_service_booking_mail(
            session,
            service_kind="tour",
            booking_id=booking_id,
            kind=kind,
            settings=settings,
        )


@router.get("/tours", response_model=list[TourListOut])
async def list_tours(db: DbSession) -> list[Tour]:
    result = await db.execute(
        select(Tour)
        .where(Tour.is_active.is_(True))
        .order_by(Tour.priority.desc(), Tour.name.asc())
    )
    return list(result.scalars().all())


@router.get("/tours/{slug}", response_model=TourOut)
async def get_tour(slug: str, db: DbSession) -> Tour:
    result = await db.execute(
        select(Tour).where(Tour.slug == slug, Tour.is_active.is_(True))
    )
    tour = result.scalar_one_or_none()
    if tour is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tour not found")
    return tour


@router.post(
    "/tour-bookings",
    response_model=TourBookingCreateOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_booking(
    body: TourBookingCreateIn,
    request: Request,
    background_tasks: BackgroundTasks,
    db: DbSession,
    settings: AppSettings,
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> TourBookingCreateOut:
    rate_limiter.hit(f"tour-booking:ip:{client_ip(request)}", limit=10)
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

        booking = await create_tour_booking(
            db,
            tour_id=body.tour_id,
            tour_date=body.tour_date,
            guests=body.guests,
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

    background_tasks.add_task(_bg_tour_mail, booking.id, "confirmation", settings)
    success_url = issue_signed_success_url(
        settings,
        booking_id=booking.id,
        path_template=settings.tour_success_path_template,
    )
    return TourBookingCreateOut(
        booking=TourBookingOut.model_validate(booking),
        success_url=success_url,
    )


@router.get("/tour-bookings/{booking_id}", response_model=TourBookingOut)
async def get_tour_booking(
    booking_id: int,
    db: DbSession,
    settings: AppSettings,
    expires: int = Query(..., description="Unix expiry from signed success URL"),
    signature: str = Query(..., description="HMAC signature from signed success URL"),
) -> TourBooking:
    """Full tour booking detail — requires valid temporary signature (≈24h)."""
    ok = verify_signed_booking_access(
        settings=settings,
        booking_id=booking_id,
        expires=expires,
        signature=signature,
        path_template=settings.tour_success_path_template,
    )
    if not ok:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Invalid or expired signature"
        )
    booking = await db.get(TourBooking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking
