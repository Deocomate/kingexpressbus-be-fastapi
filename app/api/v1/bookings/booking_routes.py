"""Public booking create/list/detail endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import JSONResponse

from app.api.v1.bookings._shared import (
    bg_mail,
    booking_out,
    issue_success_url,
    success_path_template,
)
from app.core.deps import (
    AppSettings,
    DbSession,
    get_current_user,
    get_current_user_optional,
)
from app.core.rate_limit import client_ip, rate_limiter
from app.db.models import User
from app.schemas.booking import (
    BookingCreateIn,
    BookingCreateOut,
    BookingOut,
    BookingReceiptOut,
    PriceChangedOut,
)
from app.services import booking_admin_query as booking_query
from app.services import booking_creation, customer_accounts, signed_urls
from app.services.booking_shared import BookingError, PriceChangedError

router = APIRouter(tags=["bookings"])


@router.post(
    "/bookings",
    response_model=BookingCreateOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_booking(
    body: BookingCreateIn,
    request: Request,
    background_tasks: BackgroundTasks,
    db: DbSession,
    settings: AppSettings,
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> BookingCreateOut | JSONResponse:
    rate_limiter.hit(f"booking:ip:{client_ip(request)}", limit=10)
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
            user_id=booking_user_id,
        )
        await db.commit()
        await db.refresh(booking)
    except PriceChangedError as exc:
        await db.rollback()
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=PriceChangedOut(
                submitted_total=exc.submitted_total,
                breakdown=exc.breakdown,
            ).model_dump(),
        )
    except BookingError as exc:
        await db.rollback()
        raise HTTPException(exc.status_code, detail=exc.message) from exc

    success_url = issue_success_url(settings, booking.id)
    background_tasks.add_task(bg_mail, booking.id, "confirmation", settings)
    return BookingCreateOut(
        booking_id=booking.id,
        booking_code=booking.booking_code,
        success_url=success_url,
        booking=booking_out(booking, success_url),
    )


@router.get("/bookings/mine", response_model=list[BookingOut])
async def list_my_bookings(
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> list[BookingOut]:
    bookings = await booking_query.list_bookings_for_user(db, user.id)
    return [booking_out(b) for b in bookings]


@router.get("/bookings/by-code/{code}", response_model=BookingReceiptOut)
async def get_booking_receipt_by_code(code: str, db: DbSession) -> BookingReceiptOut:
    """Public receipt — no customer PII (use signed GET /bookings/{id} for full detail)."""
    booking = await booking_query.get_booking_by_code(db, code)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return BookingReceiptOut.model_validate(booking)


@router.get("/bookings/{booking_id}", response_model=BookingOut)
async def get_booking_signed(
    booking_id: int,
    db: DbSession,
    settings: AppSettings,
    expires: int = Query(..., description="Unix expiry from signed success URL"),
    signature: str = Query(..., description="HMAC signature from signed success URL"),
) -> BookingOut:
    """Full booking detail — requires valid temporary signature (≈24h)."""
    ok = signed_urls.verify_success_token(
        booking_id=booking_id,
        expires=expires,
        signature=signature,
        path_template=success_path_template(settings),
        signing_key=settings.success_url_signing_key,
    )
    if not ok:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Invalid or expired signature"
        )
    booking = await booking_query.get_booking_by_id(db, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking_out(booking)
