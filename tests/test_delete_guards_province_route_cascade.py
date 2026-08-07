"""Regression: province delete guard must also block via the route province link.

A route's province_start_id/province_end_id cascade-delete independently of its
stops' district->province chain (stops can sit in a different province than the
route's declared start/end, e.g. shared hub stops). Deleting a province that is
only referenced through that route-level link, with a booking on one of its
trips, must be blocked exactly like the district/stop path already is.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import insert

from app.db.models import Booking, Bus, District, DistrictType, Province, Route, Stop, Trip
from app.db.session import AsyncSessionLocal

pytestmark = pytest.mark.asyncio


def _name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def test_delete_province_blocked_by_route_only_booking(admin_client) -> None:
    # Province used only as the route's start/end, with no stops of its own.
    route_province = await admin_client.post(
        "/api/v1/admin/provinces", json={"name": _name("route-province")}
    )
    route_province_id = route_province.json()["id"]
    other_province = await admin_client.post(
        "/api/v1/admin/provinces", json={"name": _name("other-province")}
    )

    route = await admin_client.post(
        "/api/v1/admin/routes",
        json={
            "province_start_id": route_province_id,
            "province_end_id": other_province.json()["id"],
            "name": _name("route"),
            "price_default": 100000,
        },
    )
    route_id = route.json()["id"]

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
            "price": 100000,
        },
    )
    trip_id = trip.json()["id"]

    # A pickup/dropoff stop deliberately outside route_province's district tree —
    # this is what makes the district/stop path blind to this booking.
    dtype = await admin_client.post("/api/v1/admin/district-types", json={"name": _name("dtype")})
    district = await admin_client.post(
        "/api/v1/admin/districts",
        json={
            "province_id": other_province.json()["id"],
            "district_type_id": dtype.json()["id"],
            "name": _name("district"),
        },
    )
    stop = await admin_client.post(
        "/api/v1/admin/stops",
        json={"district_id": district.json()["id"], "name": _name("stop"), "address": "1 St"},
    )
    stop_id = stop.json()["id"]

    async with AsyncSessionLocal() as db:
        await db.execute(
            insert(Booking).values(
                trip_id=trip_id,
                booking_code=_name("BK"),
                customer_name="Test",
                customer_phone="0900000000",
                pickup_stop_id=stop_id,
                dropoff_stop_id=stop_id,
                quantity=1,
                base_unit_price=100000,
                global_surcharge_unit=0,
                route_surcharge_unit=0,
                final_unit_price=100000,
                total_surcharge_amount=0,
                total_price=100000,
                status="pending",
                payment_method="cash_on_pickup",
                payment_status="unpaid",
                booking_date="2027-01-01",
            )
        )
        await db.commit()

    r = await admin_client.delete(f"/api/v1/admin/provinces/{route_province_id}")
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["booking_count"] == 1

    # cleanup, avoid leaking state to other tests in this session-scoped DB
    async with AsyncSessionLocal() as db:
        await db.execute(Booking.__table__.delete().where(Booking.trip_id == trip_id))
        await db.commit()
    await admin_client.delete(f"/api/v1/admin/trips/{trip_id}")
    await admin_client.delete(f"/api/v1/admin/routes/{route_id}")
    await admin_client.delete(f"/api/v1/admin/buses/{bus.json()['id']}")
    await admin_client.delete(f"/api/v1/admin/provinces/{route_province_id}")
    await admin_client.delete(f"/api/v1/admin/stops/{stop_id}")
    await admin_client.delete(f"/api/v1/admin/districts/{district.json()['id']}")
    await admin_client.delete(f"/api/v1/admin/district-types/{dtype.json()['id']}")
    await admin_client.delete(f"/api/v1/admin/provinces/{other_province.json()['id']}")
