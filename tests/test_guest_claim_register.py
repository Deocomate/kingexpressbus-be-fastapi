"""Guest claim-on-register + email verification + guest booking linking."""

from __future__ import annotations

import re
import uuid
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.application.auth import customer_accounts
from app.core.rate_limit import rate_limiter
from app.core.security import hash_password, verify_password
from app.infrastructure.mail.mail_sender import RecordingMailSender, set_mail_sender
from app.infrastructure.persistence.models import Booking, User
from app.infrastructure.persistence.session import AsyncSessionLocal
from app.main import app

pytestmark = pytest.mark.asyncio

ORIGIN = "http://localhost:3000"


def _name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _email(prefix: str = "guest") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


def _extract_code(html: str) -> str:
    match = re.search(r"letter-spacing:6px\">(\d{4})</p>", html)
    assert match, f"code not found in mail html: {html[:200]}"
    return match.group(1)


@pytest.fixture
async def public_client() -> httpx.AsyncClient:
    rate_limiter._hits.clear()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"Origin": ORIGIN},
    ) as client:
        yield client


@pytest.fixture
def mail_recorder():
    recorder = RecordingMailSender()
    set_mail_sender(recorder)
    yield recorder
    set_mail_sender(None)


async def _seed_guest_user(*, email: str, name: str = "Guest User") -> int:
    async with AsyncSessionLocal() as db:
        user = User(
            name=name,
            email=email.lower(),
            phone="0900000999",
            password=None,
            role="guest",
            email_verified_at=None,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id


async def _seed_customer_user(*, email: str, password: str = "Password1!") -> int:
    from datetime import UTC, datetime

    async with AsyncSessionLocal() as db:
        user = User(
            name="Existing Customer",
            email=email.lower(),
            phone="0900000888",
            password=hash_password(password),
            role="customer",
            email_verified_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id


async def _cleanup_users(*emails: str) -> None:
    async with AsyncSessionLocal() as db:
        for email in emails:
            user = await customer_accounts.get_user_by_email(db, email)
            if user is None:
                continue
            await db.execute(
                Booking.__table__.delete().where(Booking.user_id == user.id)
            )
            await db.execute(
                Booking.__table__.delete().where(
                    Booking.customer_email == email.lower()
                )
            )
            await db.delete(user)
        await db.commit()


async def test_ensure_customer_user_creates_guest() -> None:
    email = _email("ensure")
    try:
        async with AsyncSessionLocal() as db:
            user = await customer_accounts.ensure_customer_user(
                db,
                name="Alice Guest",
                email=email,
                phone="0912345678",
            )
            await db.commit()
            await db.refresh(user)
            assert user.id is not None
            assert user.email == email.lower()
            assert user.password is None
            assert user.role == "guest"

            again = await customer_accounts.ensure_customer_user(
                db,
                name="Alice Updated",
                email=email,
                phone="0987654321",
            )
            await db.commit()
            assert again.id == user.id
            assert again.name == "Alice Updated"
            assert again.phone == "0987654321"
    finally:
        await _cleanup_users(email)


async def test_register_claims_guest_requires_verification(
    public_client: httpx.AsyncClient,
    mail_recorder: RecordingMailSender,
) -> None:
    email = _email("claim")
    guest_id = await _seed_guest_user(email=email, name="Old Guest")
    try:
        r = await public_client.post(
            "/api/v1/auth/register",
            json={
                "name": "Claimed Name",
                "email": email,
                "password": "Password1!",
                "phone": "0911111111",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["email"] == email.lower()
        assert body["verification_required"] is True
        assert "set-cookie" not in {k.lower() for k in r.headers.keys()} or (
            "session" not in r.headers.get("set-cookie", "").lower()
            and public_client.cookies.get("session") is None
        )

        assert len(mail_recorder.sent) >= 1
        code = _extract_code(mail_recorder.sent[-1]["html"])

        # Login blocked until verified
        blocked = await public_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "Password1!"},
        )
        assert blocked.status_code == 403, blocked.text
        assert blocked.json()["detail"] == "Email not verified"

        verified = await public_client.post(
            "/api/v1/auth/verify-email",
            json={"email": email, "code": code},
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["id"] == guest_id
        assert verified.json()["role"] == "customer"

        async with AsyncSessionLocal() as db:
            user = await db.get(User, guest_id)
            assert user is not None
            assert user.email_verified_at is not None
            assert verify_password("Password1!", user.password)

        login = await public_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "Password1!"},
        )
        assert login.status_code == 200, login.text
    finally:
        await _cleanup_users(email)


async def test_register_rejects_existing_password_account(
    public_client: httpx.AsyncClient,
) -> None:
    email = _email("taken")
    await _seed_customer_user(email=email)
    try:
        r = await public_client.post(
            "/api/v1/auth/register",
            json={
                "name": "Someone Else",
                "email": email,
                "password": "Password1!",
            },
        )
        assert r.status_code == 422, r.text
        assert r.json()["detail"] == "Email already registered"
    finally:
        await _cleanup_users(email)


async def _scaffold_bookable_trip(admin_client) -> tuple[int, int, int, int]:
    """Return (trip_id, pickup_stop_id, dropoff_stop_id, price)."""
    start = await admin_client.post(
        "/api/v1/admin/provinces", json={"name": _name("province")}
    )
    end = await admin_client.post(
        "/api/v1/admin/provinces", json={"name": _name("province")}
    )
    route = await admin_client.post(
        "/api/v1/admin/routes",
        json={
            "province_start_id": start.json()["id"],
            "province_end_id": end.json()["id"],
            "name": _name("route"),
            "price_default": 150000,
        },
    )
    route_id = route.json()["id"]

    dtype = await admin_client.post(
        "/api/v1/admin/district-types", json={"name": _name("dtype")}
    )
    district = await admin_client.post(
        "/api/v1/admin/districts",
        json={
            "province_id": start.json()["id"],
            "district_type_id": dtype.json()["id"],
            "name": _name("district"),
        },
    )
    pickup = await admin_client.post(
        "/api/v1/admin/stops",
        json={
            "district_id": district.json()["id"],
            "name": _name("pickup"),
            "address": "Pickup St",
        },
    )
    dropoff = await admin_client.post(
        "/api/v1/admin/stops",
        json={
            "district_id": district.json()["id"],
            "name": _name("dropoff"),
            "address": "Dropoff St",
        },
    )
    await admin_client.post(
        f"/api/v1/admin/routes/{route_id}/stops",
        json={"stop_id": pickup.json()["id"], "stop_type": "pickup", "priority": 2},
    )
    await admin_client.post(
        f"/api/v1/admin/routes/{route_id}/stops",
        json={"stop_id": dropoff.json()["id"], "stop_type": "dropoff", "priority": 1},
    )

    bus = await admin_client.post(
        "/api/v1/admin/buses", json={"name": _name("bus"), "seat_count": 16}
    )
    trip = await admin_client.post(
        "/api/v1/admin/trips",
        json={
            "bus_id": bus.json()["id"],
            "route_id": route_id,
            "start_time": "08:00:00",
            "end_time": "12:00:00",
            "price": 150000,
        },
    )
    return (
        trip.json()["id"],
        pickup.json()["id"],
        dropoff.json()["id"],
        150000,
    )


async def test_guest_booking_links_user_and_claim_shows_in_mine(
    admin_client,
    public_client: httpx.AsyncClient,
    mail_recorder: RecordingMailSender,
) -> None:
    email = _email("book")
    trip_id, pickup_id, dropoff_id, price = await _scaffold_bookable_trip(admin_client)
    booking_date = (date.today() + timedelta(days=14)).isoformat()

    try:
        create = await public_client.post(
            "/api/v1/bookings",
            json={
                "trip_id": trip_id,
                "booking_date": booking_date,
                "quantity": 1,
                "customer_name": "Guest Booker",
                "customer_phone": "0901234567",
                "customer_email": email,
                "pickup_stop_id": pickup_id,
                "dropoff_stop_id": dropoff_id,
                "total_price": price,
                "payment_method": "cash_on_pickup",
            },
        )
        assert create.status_code == 201, create.text
        booking_id = create.json()["booking_id"]

        async with AsyncSessionLocal() as db:
            booking = await db.get(Booking, booking_id)
            assert booking is not None
            assert booking.user_id is not None
            user = await db.get(User, booking.user_id)
            assert user is not None
            assert user.email == email.lower()
            assert user.password is None
            assert user.role == "guest"
            linked_user_id = user.id

        async with AsyncSessionLocal() as db:
            orphan = Booking(
                booking_code=_name("ORPHAN")[:16].upper(),
                user_id=None,
                trip_id=trip_id,
                booking_date=date.today() + timedelta(days=21),
                customer_name="Orphan Guest",
                customer_email=email.lower(),
                customer_phone="0901234567",
                pickup_stop_id=pickup_id,
                dropoff_stop_id=dropoff_id,
                quantity=1,
                base_unit_price=price,
                global_surcharge_unit=0,
                route_surcharge_unit=0,
                final_unit_price=price,
                total_surcharge_amount=0,
                total_price=price,
                status="pending",
                payment_method="cash_on_pickup",
                payment_status="unpaid",
            )
            db.add(orphan)
            await db.commit()
            orphan_id = orphan.id

        reg = await public_client.post(
            "/api/v1/auth/register",
            json={
                "name": "Guest Booker",
                "email": email,
                "password": "Password1!",
                "phone": "0901234567",
            },
        )
        assert reg.status_code == 201, reg.text
        code = _extract_code(mail_recorder.sent[-1]["html"])

        verified = await public_client.post(
            "/api/v1/auth/verify-email",
            json={"email": email, "code": code},
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["id"] == linked_user_id
        assert verified.json()["role"] == "customer"

        mine = await public_client.get("/api/v1/bookings/mine")
        assert mine.status_code == 200, mine.text
        mine_ids = {b["id"] for b in mine.json()}
        assert booking_id in mine_ids
        assert orphan_id in mine_ids

        async with AsyncSessionLocal() as db:
            orphan_row = await db.get(Booking, orphan_id)
            assert orphan_row is not None
            assert orphan_row.user_id == linked_user_id
    finally:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Booking).where(Booking.trip_id == trip_id)
            )
            for row in result.scalars().all():
                await db.delete(row)
            await db.commit()
        await _cleanup_users(email)
        await admin_client.delete(f"/api/v1/admin/trips/{trip_id}")
