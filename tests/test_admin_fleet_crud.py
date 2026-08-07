"""Admin CRUD coverage: bus-services, buses (+ pivot service_ids)."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.asyncio


def _name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def test_bus_service_crud(admin_client) -> None:
    name = _name("service")
    r = await admin_client.post("/api/v1/admin/bus-services", json={"name": name})
    assert r.status_code == 201, r.text
    item_id = r.json()["id"]

    r = await admin_client.get("/api/v1/admin/bus-services", params={"q": name})
    assert r.status_code == 200
    assert any(i["id"] == item_id for i in r.json()["items"])

    updated_name = _name("service-upd")
    r = await admin_client.put(
        f"/api/v1/admin/bus-services/{item_id}", json={"name": updated_name}
    )
    assert r.status_code == 200
    assert r.json()["name"] == updated_name

    r = await admin_client.delete(f"/api/v1/admin/bus-services/{item_id}")
    assert r.status_code == 200


async def test_bus_crud_with_service_pivot_and_reorder(admin_client) -> None:
    svc1 = await admin_client.post("/api/v1/admin/bus-services", json={"name": _name("svc")})
    svc2 = await admin_client.post("/api/v1/admin/bus-services", json={"name": _name("svc")})
    svc1_id, svc2_id = svc1.json()["id"], svc2.json()["id"]

    name = _name("bus")
    r = await admin_client.post(
        "/api/v1/admin/buses",
        json={
            "name": name,
            "model_name": "Limousine 34",
            "seat_count": 34,
            "service_ids": [svc1_id],
        },
    )
    assert r.status_code == 201, r.text
    bus = r.json()
    bus_id = bus["id"]
    assert bus["service_ids"] == [svc1_id]

    r = await admin_client.get(f"/api/v1/admin/buses/{bus_id}")
    assert r.status_code == 200
    assert r.json()["service_ids"] == [svc1_id]

    r = await admin_client.put(
        f"/api/v1/admin/buses/{bus_id}",
        json={
            "name": name,
            "model_name": "Limousine 34 VIP",
            "seat_count": 30,
            "service_ids": [svc1_id, svc2_id],
        },
    )
    assert r.status_code == 200, r.text
    assert sorted(r.json()["service_ids"]) == sorted([svc1_id, svc2_id])
    assert r.json()["seat_count"] == 30

    r = await admin_client.post("/api/v1/admin/buses/reorder", json={"ids": [bus_id]})
    assert r.status_code == 200, r.text

    r = await admin_client.delete(f"/api/v1/admin/buses/{bus_id}")
    assert r.status_code == 200

    r = await admin_client.delete(f"/api/v1/admin/bus-services/{svc1_id}")
    assert r.status_code == 200
    r = await admin_client.delete(f"/api/v1/admin/bus-services/{svc2_id}")
    assert r.status_code == 200
