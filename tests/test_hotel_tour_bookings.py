"""Hotel + tour booking creation, inventory, and admin confirm."""

from __future__ import annotations

from datetime import date, timedelta

import httpx
import pytest
from httpx import AsyncClient

from app.core.rate_limit import rate_limiter
from app.main import app

ORIGIN = "http://localhost:3000"


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


async def _ensure_hotel_seed(client: AsyncClient) -> dict:
    listed = await client.get("/api/v1/admin/hotels")
    assert listed.status_code == 200
    items = listed.json()["items"]
    if items:
        hotel = items[0]
        rooms = await client.get(f"/api/v1/admin/hotels/{hotel['id']}/rooms")
        assert rooms.status_code == 200
        room_items = rooms.json()["items"]
        if room_items:
            return {"hotel": hotel, "room": room_items[0]}

    created = await client.post(
        "/api/v1/admin/hotels",
        json={
            "name": "Test Hotel",
            "slug": "test-hotel",
            "address": "Sa Pa",
            "is_active": True,
        },
    )
    assert created.status_code == 201, created.text
    hotel = created.json()
    room_res = await client.post(
        f"/api/v1/admin/hotels/{hotel['id']}/rooms",
        json={
            "name": "King Room",
            "slug": "king-room",
            "capacity_adults": 2,
            "base_price": 450000,
            "sale_price": 405000,
            "breakfast_price": 100000,
            "inventory_count": 2,
            "is_active": True,
        },
    )
    assert room_res.status_code == 201, room_res.text
    return {"hotel": hotel, "room": room_res.json()}


async def _ensure_tour_seed(client: AsyncClient) -> dict:
    listed = await client.get("/api/v1/admin/tours")
    assert listed.status_code == 200
    items = listed.json()["items"]
    if items:
        return items[0]
    created = await client.post(
        "/api/v1/admin/tours",
        json={
            "name": "Test Tour",
            "slug": "test-tour",
            "base_price": 350000,
            "max_guests": 5,
            "is_active": True,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


@pytest.mark.asyncio
async def test_public_hotel_slug_and_booking_cash(
    admin_client: AsyncClient, public_client: AsyncClient
):
    seeded = await _ensure_hotel_seed(admin_client)
    room = seeded["room"]
    hotel = seeded["hotel"]

    detail = await public_client.get(f"/api/v1/hotels/{hotel['slug']}")
    assert detail.status_code == 200
    assert detail.json()["name"] == hotel["name"]

    missing = await public_client.get("/api/v1/hotels/does-not-exist")
    assert missing.status_code == 404

    check_in = (date.today() + timedelta(days=3)).isoformat()
    check_out = (date.today() + timedelta(days=4)).isoformat()
    total = int(room["sale_price"]) * 1 * 1

    created = await public_client.post(
        "/api/v1/hotel-bookings",
        json={
            "room_id": room["id"],
            "check_in": check_in,
            "check_out": check_out,
            "rooms_count": 1,
            "adults": 1,
            "children": 0,
            "breakfast_count": 0,
            "customer_name": "Hotel Guest",
            "customer_email": "hotel.guest@example.com",
            "customer_phone": "0900000001",
            "payment_method": "cash_at_property",
            "total_price": total,
        },
    )
    assert created.status_code == 201, created.text
    booking = created.json()["booking"]
    assert booking["status"] == "pending"
    assert booking["booking_code"].startswith("HT-")

    over = await public_client.post(
        "/api/v1/hotel-bookings",
        json={
            "room_id": room["id"],
            "check_in": check_in,
            "check_out": check_out,
            "rooms_count": 2,
            "adults": 1,
            "children": 0,
            "breakfast_count": 0,
            "customer_name": "Overflow",
            "customer_email": "overflow@example.com",
            "payment_method": "cash_at_property",
            "total_price": total * 2,
        },
    )
    assert over.status_code == 409

    confirm = await admin_client.post(
        f"/api/v1/admin/hotel-bookings/{booking['id']}/confirm"
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["booking"]["status"] == "confirmed"


@pytest.mark.asyncio
async def test_public_tour_booking_and_confirm(
    admin_client: AsyncClient, public_client: AsyncClient
):
    tour = await _ensure_tour_seed(admin_client)
    detail = await public_client.get(f"/api/v1/tours/{tour['slug']}")
    assert detail.status_code == 200

    tour_date = (date.today() + timedelta(days=5)).isoformat()
    total = int(tour["base_price"]) * 2
    created = await public_client.post(
        "/api/v1/tour-bookings",
        json={
            "tour_id": tour["id"],
            "tour_date": tour_date,
            "guests": 2,
            "customer_name": "Tour Guest",
            "customer_email": "tour.guest@example.com",
            "payment_method": "bank_transfer",
            "total_price": total,
        },
    )
    assert created.status_code == 201, created.text
    booking = created.json()["booking"]
    assert booking["booking_code"].startswith("TR-")

    confirm = await admin_client.post(
        f"/api/v1/admin/tour-bookings/{booking['id']}/confirm"
    )
    assert confirm.status_code == 200
    assert confirm.json()["booking"]["status"] == "confirmed"
