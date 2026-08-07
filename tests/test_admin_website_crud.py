"""Admin CRUD coverage: web-profiles (read/update only) + menus (full tree CRUD)."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.asyncio


def _name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def test_web_profile_list_get_update(admin_client) -> None:
    r = await admin_client.get("/api/v1/admin/web-profiles")
    assert r.status_code == 200
    profiles = r.json()
    assert len(profiles) >= 1
    profile_id = profiles[0]["id"]

    r = await admin_client.get(f"/api/v1/admin/web-profiles/{profile_id}")
    assert r.status_code == 200

    new_hotline = "0900-111-222"
    r = await admin_client.put(
        f"/api/v1/admin/web-profiles/{profile_id}", json={"hotline": new_hotline}
    )
    assert r.status_code == 200, r.text
    assert r.json()["hotline"] == new_hotline

    r = await admin_client.get(f"/api/v1/admin/web-profiles/{profile_id}")
    assert r.json()["hotline"] == new_hotline


async def test_web_profile_get_missing_404(admin_client) -> None:
    r = await admin_client.get("/api/v1/admin/web-profiles/999999999")
    assert r.status_code == 404


async def test_menu_crud_and_tree_reorder(admin_client) -> None:
    parent_name = _name("menu-parent")
    r = await admin_client.post("/api/v1/admin/menus", json={"name": parent_name})
    assert r.status_code == 201, r.text
    parent = r.json()
    parent_id = parent["id"]
    assert parent["parent_id"] == -1

    child_name = _name("menu-child")
    r = await admin_client.post(
        "/api/v1/admin/menus", json={"name": child_name, "parent_id": parent_id}
    )
    assert r.status_code == 201, r.text
    child_id = r.json()["id"]

    r = await admin_client.get("/api/v1/admin/menus")
    assert r.status_code == 200
    ids = {m["id"] for m in r.json()}
    assert {parent_id, child_id} <= ids

    updated_name = _name("menu-upd")
    r = await admin_client.put(
        f"/api/v1/admin/menus/{parent_id}", json={"name": updated_name}
    )
    assert r.status_code == 200
    assert r.json()["name"] == updated_name

    # a menu cannot be its own parent
    r = await admin_client.put(
        f"/api/v1/admin/menus/{parent_id}",
        json={"name": updated_name, "parent_id": parent_id},
    )
    assert r.status_code == 422

    # deleting a parent with children is blocked
    r = await admin_client.delete(f"/api/v1/admin/menus/{parent_id}")
    assert r.status_code == 409

    r = await admin_client.delete(f"/api/v1/admin/menus/{child_id}")
    assert r.status_code == 200
    r = await admin_client.delete(f"/api/v1/admin/menus/{parent_id}")
    assert r.status_code == 200


async def test_menu_tree_reorder_requires_full_table(admin_client) -> None:
    name = _name("menu-solo")
    r = await admin_client.post("/api/v1/admin/menus", json={"name": name})
    menu_id = r.json()["id"]

    r = await admin_client.post(
        "/api/v1/admin/menus/reorder-tree",
        json={"items": [{"id": menu_id, "parent_id": -1, "priority": 1}]},
    )
    assert r.status_code == 200, r.text

    r = await admin_client.post(
        "/api/v1/admin/menus/reorder-tree",
        json={
            "items": [
                {"id": menu_id, "parent_id": -1, "priority": 1},
                {"id": menu_id + 999_999, "parent_id": -1, "priority": 2},
            ]
        },
    )
    assert r.status_code == 422

    r = await admin_client.delete(f"/api/v1/admin/menus/{menu_id}")
    assert r.status_code == 200
