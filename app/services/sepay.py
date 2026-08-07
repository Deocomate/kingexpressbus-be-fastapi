"""SePay checkout signature + IPN handling.

Slightly over the ~200-line guideline (234) intentionally: signing and IPN
verification share the same HMAC secret handling and are one cohesive protocol
concern, not a natural split boundary.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import Booking
from app.services.booking_shared import _utcnow

logger = logging.getLogger(__name__)

ALLOWED_SIGN_FIELDS = (
    "order_amount",
    "merchant",
    "currency",
    "operation",
    "order_description",
    "order_invoice_number",
    "customer_id",
    "payment_method",
    "success_url",
    "error_url",
    "cancel_url",
)


def sign_fields(fields: dict[str, Any], secret_key: str) -> str:
    """Doc algorithm: join allowed fields in order, HMAC-SHA256, base64."""
    signed: list[str] = []
    for field in ALLOWED_SIGN_FIELDS:
        if field not in fields:
            continue
        signed.append(f"{field}={fields[field]}")
    signed_string = ",".join(signed)
    digest = hmac.new(
        secret_key.encode("utf-8"),
        signed_string.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def signed_string_for_fields(fields: dict[str, Any]) -> str:
    """Expose the pre-HMAC string for golden-vector tests."""
    parts: list[str] = []
    for field in ALLOWED_SIGN_FIELDS:
        if field not in fields:
            continue
        parts.append(f"{field}={fields[field]}")
    return ",".join(parts)


def verify_ipn_secret(header_secret: str | None, secret_key: str) -> bool:
    if not secret_key or not isinstance(header_secret, str):
        return False
    return hmac.compare_digest(secret_key, header_secret)


def normalize_amount(amount: Any) -> int:
    try:
        return round(float(amount))
    except (TypeError, ValueError):
        return 0


def checkout_init_url(settings: Settings) -> str:
    if settings.sepay_checkout_url:
        return settings.sepay_checkout_url
    if settings.sepay_environment == "production":
        return "https://pay.sepay.vn/v1/checkout/init"
    return "https://pay-sandbox.sepay.vn/v1/checkout/init"


def build_checkout_fields(
    booking: Booking,
    settings: Settings,
) -> dict[str, str]:
    code = booking.booking_code
    base = settings.frontend_base_url.rstrip("/")
    return {
        "merchant": settings.sepay_merchant_id,
        "currency": "VND",
        "payment_method": "BANK_TRANSFER",
        "order_amount": str(int(booking.total_price)),
        "operation": "PURCHASE",
        "order_description": f"Thanh toan ve xe King Express Bus - Code: {code}",
        "order_invoice_number": code,
        "success_url": f"{base}/dat-ve/sepay/thanh-cong/{code}",
        "error_url": f"{base}/dat-ve/sepay/that-bai/{code}",
        "cancel_url": f"{base}/dat-ve/sepay/huy/{code}",
    }


def create_checkout_html(booking: Booking, settings: Settings) -> str:
    if booking.status != "confirmed":
        raise PermissionError("Booking must be confirmed for SePay checkout")
    if booking.payment_method != "online_banking":
        raise PermissionError("Booking payment method must be online_banking")
    if booking.payment_status == "paid":
        raise PermissionError("Booking is already paid")

    fields = build_checkout_fields(booking, settings)
    signature = sign_fields(fields, settings.sepay_secret_key)
    action = html.escape(checkout_init_url(settings), quote=True)

    # Hidden input order matches documented sample form
    order = [
        "merchant",
        "currency",
        "payment_method",
        "order_amount",
        "operation",
        "order_description",
        "order_invoice_number",
        "success_url",
        "error_url",
        "cancel_url",
    ]
    inputs: list[str] = []
    for key in order:
        val = html.escape(str(fields[key]), quote=True)
        inputs.append(f'<input type="hidden" name="{key}" value="{val}" />')
    inputs.append(
        f'<input type="hidden" name="signature" value="{html.escape(signature, quote=True)}" />'
    )
    body = "\n".join(inputs)
    return (
        f'<form id="sepay-checkout-form" method="POST" action="{action}">\n'
        f"{body}\n"
        f"</form>"
    )


async def handle_sepay_ipn(
    db: AsyncSession,
    *,
    payload: dict[str, Any],
    header_secret: str | None,
    settings: Settings,
) -> tuple[int, dict[str, Any], int | None]:
    """Return (http_status, body, booking_id_for_approval_mail)."""
    if not verify_ipn_secret(header_secret, settings.sepay_secret_key):
        logger.warning("SePay IPN rejected because the secret key is invalid.")
        return 401, {"error": "Unauthorized"}, None

    if payload.get("notification_type") != "ORDER_PAID":
        return 200, {"success": True}, None

    order = payload.get("order") or {}
    transaction = payload.get("transaction") or {}
    invoice_number = order.get("order_invoice_number")
    transaction_id = transaction.get("transaction_id")
    transaction_amount = normalize_amount(transaction.get("transaction_amount"))
    order_amount = normalize_amount(order.get("order_amount"))
    paid_amount = transaction_amount if transaction_amount > 0 else order_amount

    if not isinstance(invoice_number, str) or invoice_number == "":
        logger.warning(
            "SePay IPN skipped because order invoice number is missing.",
            extra={"transaction_id": transaction_id},
        )
        return 200, {"success": True}, None

    booking_id_for_mail: int | None = None
    booking = (
        await db.execute(
            select(Booking)
            .where(Booking.booking_code == invoice_number)
            .with_for_update()
        )
    ).scalar_one_or_none()

    if booking is None:
        logger.warning(
            "SePay IPN skipped because booking was not found.",
            extra={"booking_code": invoice_number, "transaction_id": transaction_id},
        )
        return 200, {"success": True}, None

    if int(booking.total_price) != paid_amount:
        logger.warning(
            "SePay IPN skipped because payment amount does not match booking total.",
            extra={
                "booking_id": booking.id,
                "booking_total": int(booking.total_price),
                "paid_amount": paid_amount,
            },
        )
        return 200, {"success": True}, None

    if booking.status != "confirmed":
        logger.warning(
            "SePay IPN skipped because booking is not confirmed for payment.",
            extra={"booking_id": booking.id, "booking_status": booking.status},
        )
        return 200, {"success": True}, None

    if booking.payment_method != "online_banking":
        logger.warning(
            "SePay IPN ignored: wrong payment method",
            extra={"booking_id": booking.id, "payment_method": booking.payment_method},
        )
        return 200, {"success": True}, None

    if booking.payment_status == "paid":
        return 200, {"success": True}, None

    booking.payment_status = "paid"
    booking.payment_transaction_id = (
        transaction_id if isinstance(transaction_id, str) else None
    )
    booking.payment_log = payload
    booking.updated_at = _utcnow()
    await db.flush()
    booking_id_for_mail = int(booking.id)

    logger.info(
        "SePay IPN marked booking as paid.",
        extra={
            "booking_id": booking_id_for_mail,
            "booking_code": invoice_number,
            "transaction_id": transaction_id,
        },
    )
    return 200, {"success": True}, booking_id_for_mail
