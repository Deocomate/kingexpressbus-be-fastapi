"""Phase 4: booking, SePay, signed URLs, mail, rate limits (mostly no DB)."""

from __future__ import annotations

import base64
import hashlib
import hmac
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.application.booking import booking_notes as notes
from app.application.booking.pricing import _reason_label
from app.core.config import Settings
from app.core.rate_limit import RateLimiter
from app.infrastructure.mail.mail import send_booking_mail
from app.infrastructure.mail.mail_sender import RecordingMailSender, set_mail_sender
from app.infrastructure.payments import sepay as sepay_svc
from app.infrastructure.storage import signed_urls
from app.main import app

client = TestClient(app)


# --- SePay signature golden vector (docs/sepay-intergration.md worked example) ---

DOC_FIELDS = {
    "order_amount": "100000",
    "merchant": "MERCHANT_123",
    "currency": "VND",
    "operation": "PURCHASE",
    "order_description": "Thanh toán đơn hàng #12345",
    "order_invoice_number": "INV_20231201_001",
    "success_url": "https://yoursite.com/payment/success",
    "error_url": "https://yoursite.com/payment/error",
    "cancel_url": "https://yoursite.com/payment/cancel",
}

DOC_SIGNED_STRING = (
    "order_amount=100000,merchant=MERCHANT_123,currency=VND,operation=PURCHASE,"
    "order_description=Thanh toán đơn hàng #12345,"
    "order_invoice_number=INV_20231201_001,"
    "success_url=https://yoursite.com/payment/success,"
    "error_url=https://yoursite.com/payment/error,"
    "cancel_url=https://yoursite.com/payment/cancel"
)


def test_sepay_signed_string_matches_doc_worked_example() -> None:
    assert sepay_svc.signed_string_for_fields(DOC_FIELDS) == DOC_SIGNED_STRING


def test_sepay_sign_fields_hmac_base64() -> None:
    secret = "test-secret-key"
    sig = sepay_svc.sign_fields(DOC_FIELDS, secret)
    expected = base64.b64encode(
        hmac.new(
            secret.encode(),
            DOC_SIGNED_STRING.encode(),
            hashlib.sha256,
        ).digest()
    ).decode()
    assert sig == expected


def test_sepay_checkout_requires_confirmed() -> None:
    settings = Settings(
        sepay_merchant_id="M1",
        sepay_secret_key="secret",
        frontend_base_url="http://localhost:3000",
    )
    booking = SimpleNamespace(
        status="pending",
        payment_method="online_banking",
        payment_status="unpaid",
        total_price=100000,
        booking_code="ABCDEFGH12345678",
    )
    with pytest.raises(PermissionError):
        sepay_svc.create_checkout_html(booking, settings)  # type: ignore[arg-type]


def test_sepay_checkout_html_confirmed() -> None:
    settings = Settings(
        sepay_merchant_id="M1",
        sepay_secret_key="secret",
        frontend_base_url="http://localhost:3000",
        sepay_checkout_url="https://pay-sandbox.sepay.vn/v1/checkout/init",
    )
    booking = SimpleNamespace(
        status="confirmed",
        payment_method="online_banking",
        payment_status="unpaid",
        total_price=250000,
        booking_code="ABCDEFGH12345678",
    )
    html = sepay_svc.create_checkout_html(booking, settings)  # type: ignore[arg-type]
    assert 'id="sepay-checkout-form"' in html
    assert "order_invoice_number" in html
    assert "ABCDEFGH12345678" in html
    assert "signature" in html


# --- Signed success URLs ---


def test_signed_success_url_roundtrip() -> None:
    key = "signing-key-min-32-chars-xxxxxx"
    url = signed_urls.sign_success_url(
        base_url="http://localhost:3000/dat-ve/thanh-cong/{booking}",
        booking_id=42,
        signing_key=key,
        now=1_700_000_000,
        ttl_seconds=3600,
    )
    assert "42" in url
    assert signed_urls.verify_success_url(url=url, signing_key=key, now=1_700_000_100) == 42


def test_signed_success_url_expired() -> None:
    key = "signing-key-min-32-chars-xxxxxx"
    url = signed_urls.sign_success_url(
        base_url="http://localhost:3000/dat-ve/thanh-cong/{booking}",
        booking_id=7,
        signing_key=key,
        now=1_700_000_000,
        ttl_seconds=10,
    )
    assert signed_urls.verify_success_url(url=url, signing_key=key, now=1_700_000_020) is None


def test_verify_success_token_params() -> None:
    key = "signing-key-min-32-chars-xxxxxx"
    path = "http://localhost:3000/dat-ve/thanh-cong/{booking}"
    url = signed_urls.sign_success_url(
        base_url=path, booking_id=9, signing_key=key, now=1_700_000_000, ttl_seconds=100
    )
    from urllib.parse import parse_qs, urlparse

    qs = parse_qs(urlparse(url).query)
    assert signed_urls.verify_success_token(
        booking_id=9,
        expires=int(qs["expires"][0]),
        signature=qs["signature"][0],
        path_template=path,
        signing_key=key,
        now=1_700_000_050,
    )


# --- Notes ---


def test_hotel_pickup_notes_and_extract() -> None:
    built = notes.build_hotel_pickup_notes(
        hotel_address="123 Hotel St",
        customer_notes="Call me",
    )
    assert built.startswith(notes.NOTE_HOTEL_PICKUP_PREFIX)
    assert notes.NOTE_CUSTOMER_PREFIX in built
    assert notes.extract_hotel_pickup_address(built) == "123 Hotel St"
    legacy = notes.LEGACY_NOTE_HOTEL_PICKUP_PREFIX + "Old Addr\nmore"
    assert notes.extract_hotel_pickup_address(legacy) == "Old Addr"


def test_sepay_refund_note() -> None:
    line = notes.sepay_refund_note("TXN-1")
    assert line.startswith(notes.NOTE_SEPAY_REFUND_PREFIX)
    assert "TXN-1" in line


def test_pricing_reason_label_format() -> None:
    label = _reason_label("Tet", 40000, 1000)
    assert label == "Tet (global +40,000đ, route +1,000đ)"


# --- Mail failures do not raise ---


@pytest.mark.asyncio
async def test_mail_smtp_failure_logged_not_raised() -> None:
    class Boom:
        async def send(self, *, to, subject, html):
            raise RuntimeError("smtp down")

    set_mail_sender(Boom())  # type: ignore[arg-type]
    try:
        ok = await send_booking_mail(
            kind="confirmation",
            details={
                "booking_id": 1,
                "booking_code": "X",
                "customer_email": "a@b.com",
                "customer_name": "A",
                "route_name": "R",
                "total_price": 1,
            },
            settings=Settings(),
        )
        assert ok is False
    finally:
        set_mail_sender(None)


@pytest.mark.asyncio
async def test_recording_mail_sender() -> None:
    rec = RecordingMailSender()
    set_mail_sender(rec)
    try:
        assert await send_booking_mail(
            kind="approval",
            details={
                "booking_id": 1,
                "booking_code": "X",
                "customer_email": "a@b.com",
                "customer_name": "A",
                "route_name": "R",
                "total_price": 1,
            },
            settings=Settings(admin_notify_email="admin@example.com"),
        )
        assert len(rec.sent) == 1
        assert "a@b.com" in rec.sent[0]["to"]
        assert "admin@example.com" in rec.sent[0]["to"]
    finally:
        set_mail_sender(None)


# --- IPN gate logic ---


@pytest.mark.asyncio
async def test_ipn_bad_secret_401() -> None:
    settings = Settings(sepay_secret_key="real-secret")
    db = AsyncMock()
    status, body, mail_id = await sepay_svc.handle_sepay_ipn(
        db, payload={}, header_secret="wrong", settings=settings
    )
    assert status == 401
    assert body["error"] == "Unauthorized"
    assert mail_id is None


@pytest.mark.asyncio
async def test_ipn_non_order_paid_200() -> None:
    settings = Settings(sepay_secret_key="secret")
    db = AsyncMock()
    status, body, mail_id = await sepay_svc.handle_sepay_ipn(
        db,
        payload={"notification_type": "OTHER"},
        header_secret="secret",
        settings=settings,
    )
    assert status == 200
    assert body == {"success": True}
    assert mail_id is None


@pytest.mark.asyncio
async def test_ipn_amount_mismatch_stays_unpaid() -> None:
    settings = Settings(sepay_secret_key="secret")
    booking = SimpleNamespace(
        id=1,
        total_price=100000,
        status="confirmed",
        payment_method="online_banking",
        payment_status="unpaid",
        payment_transaction_id=None,
        payment_log=None,
        updated_at=None,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = booking
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    status, body, mail_id = await sepay_svc.handle_sepay_ipn(
        db,
        payload={
            "notification_type": "ORDER_PAID",
            "order": {"order_invoice_number": "CODE1", "order_amount": 99999},
            "transaction": {"transaction_amount": 99999, "transaction_id": "t1"},
        },
        header_secret="secret",
        settings=settings,
    )
    assert status == 200
    assert mail_id is None
    assert booking.payment_status == "unpaid"


@pytest.mark.asyncio
async def test_ipn_pending_ignored() -> None:
    settings = Settings(sepay_secret_key="secret")
    booking = SimpleNamespace(
        id=2,
        total_price=100000,
        status="pending",
        payment_method="online_banking",
        payment_status="unpaid",
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = booking
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    status, body, mail_id = await sepay_svc.handle_sepay_ipn(
        db,
        payload={
            "notification_type": "ORDER_PAID",
            "order": {"order_invoice_number": "CODE2", "order_amount": 100000},
            "transaction": {"transaction_amount": 100000, "transaction_id": "t2"},
        },
        header_secret="secret",
        settings=settings,
    )
    assert status == 200
    assert mail_id is None
    assert booking.payment_status == "unpaid"


@pytest.mark.asyncio
async def test_ipn_cash_ignored() -> None:
    settings = Settings(sepay_secret_key="secret")
    booking = SimpleNamespace(
        id=3,
        total_price=100000,
        status="confirmed",
        payment_method="cash_on_pickup",
        payment_status="unpaid",
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = booking
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    status, body, mail_id = await sepay_svc.handle_sepay_ipn(
        db,
        payload={
            "notification_type": "ORDER_PAID",
            "order": {"order_invoice_number": "CODE3", "order_amount": 100000},
            "transaction": {"transaction_amount": 100000, "transaction_id": "t3"},
        },
        header_secret="secret",
        settings=settings,
    )
    assert status == 200
    assert mail_id is None


@pytest.mark.asyncio
async def test_ipn_marks_paid_and_idempotent() -> None:
    settings = Settings(sepay_secret_key="secret")
    booking = SimpleNamespace(
        id=4,
        total_price=100000,
        status="confirmed",
        payment_method="online_banking",
        payment_status="unpaid",
        payment_transaction_id=None,
        payment_log=None,
        updated_at=None,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = booking
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()

    payload = {
        "notification_type": "ORDER_PAID",
        "order": {"order_invoice_number": "CODE4", "order_amount": 100000},
        "transaction": {"transaction_amount": 100000, "transaction_id": "t4"},
    }
    status, body, mail_id = await sepay_svc.handle_sepay_ipn(
        db, payload=payload, header_secret="secret", settings=settings
    )
    assert status == 200
    assert mail_id == 4
    assert booking.payment_status == "paid"
    assert booking.payment_transaction_id == "t4"

    # replay
    status2, _, mail_id2 = await sepay_svc.handle_sepay_ipn(
        db, payload=payload, header_secret="secret", settings=settings
    )
    assert status2 == 200
    assert mail_id2 is None


# --- Rate limit ---


def test_rate_limiter_booking_11th_429() -> None:
    limiter = RateLimiter()
    for _ in range(10):
        limiter.hit("test:booking", limit=10)
    with pytest.raises(Exception) as exc:
        limiter.hit("test:booking", limit=10)
    assert exc.value.status_code == 429  # type: ignore[attr-defined]


# --- OpenAPI surface ---


def test_openapi_documents_booking_payment_surface() -> None:
    paths = client.get("/openapi.json").json()["paths"]
    expected = [
        "/api/v1/bookings",
        "/api/v1/bookings/by-code/{code}",
        "/api/v1/bookings/{booking_id}",
        "/api/v1/payments/status/{code}",
        "/api/v1/payments/sepay/checkout/{code}",
        "/api/v1/payments/sepay/ipn",
        "/api/v1/payments/sepay/return/{code}",
        "/api/v1/payments/success-url/verify",
        "/api/v1/admin/bookings/{booking_id}/confirm",
        "/api/v1/admin/bookings/{booking_id}/cancel",
        "/api/v1/admin/bookings/{booking_id}/complete",
    ]
    missing = [p for p in expected if p not in paths]
    assert missing == [], missing
    # C1: public mint endpoint must not exist
    assert "/api/v1/payments/success-url/{booking_id}" not in paths


def test_booking_create_schema_requires_pickup_or_hotel() -> None:
    from pydantic import ValidationError

    from app.presentation.schemas.booking import BookingCreateIn

    base = {
        "trip_id": 1,
        "booking_date": "2026-08-10",
        "quantity": 1,
        "customer_name": "A",
        "customer_phone": "090",
        "customer_email": "a@b.com",
        "dropoff_stop_id": 2,
        "total_price": 100000,
        "payment_method": "cash_on_pickup",
    }
    with pytest.raises(ValidationError):
        BookingCreateIn(**base)
    with pytest.raises(ValidationError):
        BookingCreateIn(**base, is_hotel_pickup=True)
    ok = BookingCreateIn(**base, pickup_stop_id=5)
    assert ok.pickup_stop_id == 5
    hotel = BookingCreateIn(
        **base, is_hotel_pickup=True, hotel_pickup_address="123 St"
    )
    assert hotel.is_hotel_pickup


def test_get_booking_requires_signature_params() -> None:
    r = client.get("/api/v1/bookings/1")
    assert r.status_code == 422  # missing expires + signature


def test_get_booking_rejects_bad_signature() -> None:
    r = client.get(
        "/api/v1/bookings/1",
        params={"expires": 9999999999, "signature": "deadbeef"},
    )
    assert r.status_code == 403



def test_ipn_endpoint_bad_secret_via_http() -> None:
    with patch(
        "app.presentation.api.v1.bookings.payment_routes.sepay_svc.handle_sepay_ipn",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = (401, {"error": "Unauthorized"}, None)
        r = client.post(
            "/api/v1/payments/sepay/ipn",
            json={"notification_type": "ORDER_PAID"},
            headers={"X-Secret-Key": "bad"},
        )
    assert r.status_code == 401


# --- Cancel / status unit with mocks ---


@pytest.mark.asyncio
async def test_cancel_paid_online_appends_refund_note() -> None:
    from app.application.booking import booking_cancel as booking_svc

    booking = MagicMock()
    booking.id = 10
    booking.status = "confirmed"
    booking.notes = None
    booking.payment_method = "online_banking"
    booking.payment_status = "paid"
    booking.payment_transaction_id = "TX-99"

    result = MagicMock()
    result.scalar_one_or_none.return_value = booking
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    out = await booking_svc.cancel_booking(
        db, 10, reason="Customer request", admin_user_id=1
    )
    assert out.email_action == "cancellation"
    assert booking.status == "cancelled"
    assert notes.NOTE_ADMIN_CANCEL_PREFIX in (booking.notes or "")
    assert notes.NOTE_SEPAY_REFUND_PREFIX in (booking.notes or "")


@pytest.mark.asyncio
async def test_cancel_twice_rejected() -> None:
    from app.application.booking import booking_cancel as booking_svc
    from app.application.booking.booking_shared import BookingError

    booking = MagicMock()
    booking.status = "cancelled"
    result = MagicMock()
    result.scalar_one_or_none.return_value = booking
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(BookingError):
        await booking_svc.cancel_booking(db, 1)


@pytest.mark.asyncio
async def test_confirm_cash_sets_approval_mail() -> None:
    from app.application.booking import booking_status as booking_svc

    booking = MagicMock()
    booking.status = "pending"
    booking.payment_method = "cash_on_pickup"
    booking.confirmed_at = None
    booking.notes = None
    result = MagicMock()
    result.scalar_one_or_none.return_value = booking
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    out = await booking_svc.update_booking_status(db, 1, "confirmed")
    assert out.email_action == "approval"
    assert booking.confirmed_at is not None


@pytest.mark.asyncio
async def test_confirm_online_sets_payment_request_mail() -> None:
    from app.application.booking import booking_status as booking_svc

    booking = MagicMock()
    booking.status = "pending"
    booking.payment_method = "online_banking"
    booking.confirmed_at = None
    result = MagicMock()
    result.scalar_one_or_none.return_value = booking
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    out = await booking_svc.update_booking_status(db, 1, "confirmed")
    assert out.email_action == "payment_request"


@pytest.mark.asyncio
async def test_reconfirm_sends_no_mail() -> None:
    from datetime import datetime

    from app.application.booking import booking_status as booking_svc

    prior = datetime(2026, 1, 1)
    booking = MagicMock()
    booking.status = "confirmed"
    booking.payment_method = "online_banking"
    booking.confirmed_at = prior
    result = MagicMock()
    result.scalar_one_or_none.return_value = booking
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    out = await booking_svc.update_booking_status(db, 1, "confirmed")
    assert out.email_action is None
    assert booking.confirmed_at == prior
