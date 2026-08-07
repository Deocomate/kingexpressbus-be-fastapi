"""Public payment status + SePay checkout/return/IPN endpoints."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.api.v1.bookings._shared import (
    bg_mail,
    issue_success_url,
    success_path_template,
)
from app.core.deps import AppSettings, DbSession
from app.core.rate_limit import client_ip, rate_limiter
from app.db.session import AsyncSessionLocal
from app.schemas.booking import (
    PaymentStatusOut,
    SepayCheckoutOut,
    SignedSuccessVerifyIn,
    SignedSuccessVerifyOut,
)
from app.services import booking_admin_query as booking_query
from app.services import sepay as sepay_svc
from app.services import signed_urls

router = APIRouter(tags=["bookings"])


@router.get("/payments/status/{code}", response_model=PaymentStatusOut)
async def payment_status(code: str, request: Request, db: DbSession) -> PaymentStatusOut:
    rate_limiter.hit(f"payment:ip:{client_ip(request)}", limit=60)
    booking = await booking_query.get_booking_by_code(db, code)
    if booking is None:
        return PaymentStatusOut(found=False)
    return PaymentStatusOut(
        found=True,
        booking_code=booking.booking_code,
        status=booking.status,
        payment_method=booking.payment_method,
        payment_status=booking.payment_status,
    )


@router.post("/payments/success-url/verify", response_model=SignedSuccessVerifyOut)
async def verify_success_url(
    body: SignedSuccessVerifyIn,
    settings: AppSettings,
) -> SignedSuccessVerifyOut:
    ok = signed_urls.verify_success_token(
        booking_id=body.booking_id,
        expires=body.expires,
        signature=body.signature,
        path_template=success_path_template(settings),
        signing_key=settings.success_url_signing_key,
    )
    return SignedSuccessVerifyOut(
        valid=ok,
        booking_id=body.booking_id if ok else None,
    )


@router.get("/payments/sepay/checkout/{code}", response_model=SepayCheckoutOut)
async def sepay_checkout_html(
    code: str,
    request: Request,
    db: DbSession,
    settings: AppSettings,
) -> SepayCheckoutOut | JSONResponse:
    rate_limiter.hit(f"payment:ip:{client_ip(request)}", limit=60)
    booking = await booking_query.get_booking_by_code(db, code)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.status == "cancelled":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Booking cancelled")
    if booking.status != "confirmed":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Booking not confirmed")
    if booking.payment_status == "paid":
        url = issue_success_url(settings, booking.id)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"already_paid": True, "success_url": url},
        )
    try:
        html_form = sepay_svc.create_checkout_html(booking, settings)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return SepayCheckoutOut(booking_code=code, html_form=html_form)


@router.get("/payments/sepay/return/{code}")
async def sepay_return(
    code: str,
    request: Request,
    settings: AppSettings,
) -> dict:
    """Poll until paid (IPN lag) then return signed success URL.

    Each attempt uses a fresh DB session so MySQL REPEATABLE READ cannot hide
    a concurrent IPN commit.
    """
    rate_limiter.hit(f"payment:ip:{client_ip(request)}", limit=60)

    booking = None
    payment_status_val = "unpaid"
    booking_id = 0
    booking_code = code

    for attempt in range(5):
        async with AsyncSessionLocal() as session:
            booking = await booking_query.get_booking_by_code(session, code)
            if booking is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
            booking_id = int(booking.id)
            booking_code = booking.booking_code
            payment_status_val = booking.payment_status
            if payment_status_val == "paid":
                break
        if attempt < 4:
            await asyncio.sleep(0.5)

    return {
        "booking_code": booking_code,
        "payment_status": payment_status_val,
        "success_url": issue_success_url(settings, booking_id),
    }


@router.post("/payments/sepay/ipn")
async def sepay_ipn(
    request: Request,
    background_tasks: BackgroundTasks,
    db: DbSession,
    settings: AppSettings,
    x_secret_key: Annotated[str | None, Header(alias="X-Secret-Key")] = None,
) -> JSONResponse:
    rate_limiter.hit(f"payment:ip:{client_ip(request)}", limit=60)
    payload = await request.json()
    http_status, body, mail_id = await sepay_svc.handle_sepay_ipn(
        db,
        payload=payload if isinstance(payload, dict) else {},
        header_secret=x_secret_key,
        settings=settings,
    )
    if http_status == 200:
        await db.commit()
        if mail_id is not None:
            background_tasks.add_task(bg_mail, mail_id, "approval", settings)
    else:
        await db.rollback()
    return JSONResponse(status_code=http_status, content=body)
