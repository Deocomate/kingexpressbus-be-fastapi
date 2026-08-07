"""Admin CRUD coverage: holiday surcharges (+ per-route additive pivot)."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.asyncio


def _name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def _make_route(admin_client) -> int:
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
    return route.json()["id"]


async def test_surcharge_crud_with_route_amounts(admin_client) -> None:
    route_id = await _make_route(admin_client)

    name = _name("surcharge")
    r = await admin_client.post(
        "/api/v1/admin/surcharges",
        json={
            "name": name,
            "reason": "Tet holiday",
            "start_date": "2027-02-01",
            "end_date": "2027-02-10",
            "global_surcharge_amount": 40000,
            "route_amounts": [{"route_id": route_id, "route_surcharge_amount": 10000}],
        },
    )
    assert r.status_code == 201, r.text
    surcharge = r.json()
    surcharge_id = surcharge["id"]
    assert surcharge["route_amounts"] == [
        {"route_id": route_id, "route_surcharge_amount": 10000}
    ]

    r = await admin_client.get("/api/v1/admin/surcharges")
    assert r.status_code == 200
    assert any(s["id"] == surcharge_id for s in r.json()["items"])

    r = await admin_client.get(f"/api/v1/admin/surcharges/{surcharge_id}")
    assert r.status_code == 200

    r = await admin_client.put(
        f"/api/v1/admin/surcharges/{surcharge_id}",
        json={
            "name": name,
            "start_date": "2027-02-01",
            "end_date": "2027-02-12",
            "global_surcharge_amount": 50000,
            "is_active": False,
            "route_amounts": [],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["global_surcharge_amount"] == 50000
    assert r.json()["is_active"] is False
    assert r.json()["route_amounts"] == []

    r = await admin_client.post(
        "/api/v1/admin/surcharges",
        json={
            "name": _name("bad"),
            "start_date": "2027-03-05",
            "end_date": "2027-03-01",
        },
    )
    assert r.status_code == 422  # end_date before start_date rejected

    r = await admin_client.delete(f"/api/v1/admin/surcharges/{surcharge_id}")
    assert r.status_code == 200

    r = await admin_client.get(f"/api/v1/admin/surcharges/{surcharge_id}")
    assert r.status_code == 404
