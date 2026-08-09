"""Additive seed: route priorities + header route menus (2026-08-09).

Safe for production. Updates ``routes.priority`` by slug and upserts curated
route dropdown menus under ``Tuyến đường``. Never truncates.

Natural keys:
- routes: ``slug`` (priority field only)
- menus: ``url`` for curated ``/tuyen-duong/...`` children
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.infrastructure.persistence.models.ops import Route
from app.infrastructure.persistence.models.website import Menu
from scripts.seeds.common import (
    insert_missing_menu_by_url,
    load_seed_rows,
)

NAME = "20260809_route_menu_priorities"
DESCRIPTION = (
    "Reassign route priorities (Sa Pa → HN corridor → others) "
    "and expand Tuyến đường header menus"
)

_ROUTE_MENU_URL_PREFIX = "/tuyen-duong/"
_PARENT_MENU_NAME = "Tuyến đường"


def _slug_from_menu_url(url: str) -> str | None:
    if not url.startswith(_ROUTE_MENU_URL_PREFIX):
        return None
    slug = url[len(_ROUTE_MENU_URL_PREFIX) :].strip("/")
    return slug or None


async def apply(
    conn: AsyncConnection,
    *,
    update_existing: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    routes_table = Route.__table__
    menus_table = Menu.__table__

    # --- Route priorities (always update when --update; insert N/A) ---
    route_counts = {"inserted": 0, "updated": 0, "skipped": 0}
    for row in load_seed_rows("routes.json"):
        slug = row["slug"]
        priority = int(row["priority"])
        existing_id = (
            await conn.execute(
                select(routes_table.c.id).where(routes_table.c.slug == slug).limit(1)
            )
        ).scalar_one_or_none()
        if existing_id is None:
            route_counts["skipped"] += 1
            continue
        if update_existing:
            route_counts["updated"] += 1
            if not dry_run:
                await conn.execute(
                    update(routes_table)
                    .where(routes_table.c.id == existing_id)
                    .values(priority=priority)
                )
        else:
            route_counts["skipped"] += 1

    # --- Resolve parent menu id (Tuyến đường) ---
    parent_id = (
        await conn.execute(
            select(menus_table.c.id)
            .where(menus_table.c.name == _PARENT_MENU_NAME)
            .order_by(menus_table.c.id.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if parent_id is None and dry_run:
        parent_id = -2

    # Live slug → route id for related_id remapping.
    slug_to_id: dict[str, int] = {}
    for row in (
        await conn.execute(select(routes_table.c.id, routes_table.c.slug))
    ).all():
        slug_to_id[str(row.slug)] = int(row.id)

    menu_rows: list[dict[str, Any]] = []
    for raw in load_seed_rows("menus.json"):
        url = raw.get("url") or ""
        slug = _slug_from_menu_url(url)
        if slug is None:
            continue
        live_route_id = slug_to_id.get(slug)
        if live_route_id is None and dry_run:
            live_route_id = int(raw.get("related_id") or 0)
        if live_route_id is None:
            # Route missing on this DB — skip menu item.
            continue
        if parent_id is None:
            raise RuntimeError(
                f"Menu parent {_PARENT_MENU_NAME!r} missing; cannot seed route menus."
            )
        payload = dict(raw)
        payload["parent_id"] = int(parent_id)
        payload["related_id"] = int(live_route_id)
        menu_rows.append(payload)

    if parent_id is None and menu_rows:
        raise RuntimeError(
            f"Menu parent {_PARENT_MENU_NAME!r} missing; cannot seed route menus."
        )

    menu_counts = await insert_missing_menu_by_url(
        conn,
        table=menus_table,
        rows=menu_rows,
        update_existing=update_existing,
        dry_run=dry_run,
    )

    return {
        "routes": route_counts,
        "menus": menu_counts,
    }
