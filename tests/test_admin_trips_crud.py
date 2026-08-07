"""Admin CRUD coverage: trips + trip-blocks."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.asyncio


def _name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def _make_route(admin_client) -> tuple[int, int, int]:
    start = await admin_client.post("/api/v1/admin/provinces", json={"name": _name("province")})
    end = await admin_client.post("/api/v1/admin/provinces", json={"name": _name("province")})
    route = await admin_client.post(
        "/api/v1/admin/routes",
        json={
            "province_start_id": start.json()["id"],
            "province_end_id": end.json()["id"],
            "name": _name("route"),
        },
    )
    return route.json()["id"], start.json()["id"], end.json()["id"]


async def _make_bus(admin_client) -> int:
    bus = await admin_client.post(
        "/api/v1/admin/buses",
        json={"name": _name("bus"), "seat_count": 16},
    )
    return bus.json()["id"]


async def test_trip_crud(admin_client) -> None:
    route_id, province_start_id, province_end_id = await _make_route(admin_client)
    bus_id = await _make_bus(admin_client)

    r = await admin_client.post(
        "/api/v1/admin/trips",
        json={
            "bus_id": bus_id,
            "route_id": route_id,
            "start_time": "08:00:00",
            "end_time": "12:00:00",
            "price": 180000,
        },
    )
    assert r.status_code == 201, r.text
    trip = r.json()
    trip_id = trip["id"]
    assert trip["price"] == 180000

    r = await admin_client.get("/api/v1/admin/trips", params={"route_id": route_id})
    assert r.status_code == 200
    listed = next(t for t in r.json()["items"] if t["id"] == trip_id)
    assert listed["route_name"]
    assert listed["bus_name"]
    assert listed["province_start_id"] == province_start_id
    assert listed["province_start_name"]
    assert listed["province_end_id"] == province_end_id
    assert listed["province_end_name"]

    r = await admin_client.get(
        "/api/v1/admin/trips",
        params={
            "province_start_id": province_start_id,
            "province_end_id": province_end_id,
        },
    )
    assert r.status_code == 200
    assert any(t["id"] == trip_id for t in r.json()["items"])

    r = await admin_client.get(
        "/api/v1/admin/trips", params={"province_id": province_start_id}
    )
    assert r.status_code == 200
    assert any(t["id"] == trip_id for t in r.json()["items"])

    r = await admin_client.get(f"/api/v1/admin/trips/{trip_id}")
    assert r.status_code == 200

    r = await admin_client.put(
        f"/api/v1/admin/trips/{trip_id}",
        json={
            "bus_id": bus_id,
            "route_id": route_id,
            "start_time": "09:00:00",
            "end_time": "13:00:00",
            "price": 190000,
            "is_active": False,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False
    assert r.json()["price"] == 190000

    r = await admin_client.delete(f"/api/v1/admin/trips/{trip_id}")
    assert r.status_code == 200

    r = await admin_client.delete(f"/api/v1/admin/routes/{route_id}")
    assert r.status_code == 200
    r = await admin_client.delete(f"/api/v1/admin/buses/{bus_id}")
    assert r.status_code == 200


async def test_trip_block_crud(admin_client) -> None:
    route_id, _, _ = await _make_route(admin_client)
    bus_id = await _make_bus(admin_client)
    trip = await admin_client.post(
        "/api/v1/admin/trips",
        json={
            "bus_id": bus_id,
            "route_id": route_id,
            "start_time": "08:00:00",
            "end_time": "12:00:00",
        },
    )
    trip_id = trip.json()["id"]

    r = await admin_client.post(
        "/api/v1/admin/trip-blocks",
        json={
            "trip_id": trip_id,
            "start_date": "2026-09-01",
            "end_date": "2026-09-03",
            "block_type": "off_day",
            "note": "Maintenance",
        },
    )
    assert r.status_code == 201, r.text
    block = r.json()
    block_id = block["id"]

    r = await admin_client.get("/api/v1/admin/trip-blocks", params={"trip_id": trip_id})
    assert r.status_code == 200
    assert any(b["id"] == block_id for b in r.json()["items"])

    r = await admin_client.put(
        f"/api/v1/admin/trip-blocks/{block_id}",
        json={
            "trip_id": trip_id,
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
            "block_type": "sold_out",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["block_type"] == "sold_out"

    r = await admin_client.post(
        "/api/v1/admin/trip-blocks",
        json={
            "trip_id": trip_id,
            "start_date": "2026-09-05",
            "end_date": "2026-09-01",
            "block_type": "off_day",
        },
    )
    assert r.status_code == 422  # end_date before start_date rejected

    r = await admin_client.delete(f"/api/v1/admin/trip-blocks/{block_id}")
    assert r.status_code == 200

    r = await admin_client.delete(f"/api/v1/admin/trips/{trip_id}")
    assert r.status_code == 200
