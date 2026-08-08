"""Additive seed: hotels, rooms, tours, and nav menus (2026-08-08).

Safe for production after ``alembic upgrade head`` (migration 0006).
Inserts missing rows by slug/url; never truncates. Re-run is idempotent.

Natural keys:
- hotels / tours: ``slug``
- hotel_rooms: ``(hotel.slug → hotel_id, room.slug)``
- menus: ``url`` for ``/khach-san`` and ``/tour`` only
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.infrastructure.persistence.models.hotel import Hotel, HotelRoom
from app.infrastructure.persistence.models.tour import Tour
from app.infrastructure.persistence.models.website import Menu
from scripts.seeds.common import (
    insert_missing_by_slug,
    insert_missing_menu_by_url,
    load_seed_rows,
)

NAME = "20260808_hotels_tours_menus"
DESCRIPTION = "Sapa Cosy hotel + rooms, placeholder Sa Pa tours, hotel/tour nav menus"

# Seed-file hotel id → slug (used to remap hotel_rooms.hotel_id on prod).
_SEED_HOTEL_ID_TO_SLUG = {1: "sapa-cosy-hotel"}

_MENU_URLS = {"/khach-san", "/tour"}


async def apply(
    conn: AsyncConnection,
    *,
    update_existing: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    hotels_table = Hotel.__table__
    rooms_table = HotelRoom.__table__
    tours_table = Tour.__table__
    menus_table = Menu.__table__

    hotel_counts = await insert_missing_by_slug(
        conn,
        table=hotels_table,
        rows=load_seed_rows("hotels.json"),
        update_existing=update_existing,
        dry_run=dry_run,
    )

    # Map seed hotel_id → live hotel_id via slug.
    seed_to_live: dict[int, int] = {}
    for seed_id, slug in _SEED_HOTEL_ID_TO_SLUG.items():
        live_id = (
            await conn.execute(
                select(hotels_table.c.id).where(hotels_table.c.slug == slug).limit(1)
            )
        ).scalar_one_or_none()
        if live_id is None and dry_run:
            # Dry-run may not have inserted yet; pretend autoincrement next id.
            live_id = -seed_id
        if live_id is None:
            raise RuntimeError(
                f"Hotel slug={slug!r} missing after hotel upsert; cannot seed rooms."
            )
        seed_to_live[seed_id] = int(live_id)

    room_counts = {"inserted": 0, "updated": 0, "skipped": 0}
    for room in load_seed_rows("hotel_rooms.json"):
        seed_hotel_id = int(room["hotel_id"])
        live_hotel_id = seed_to_live[seed_hotel_id]
        if live_hotel_id < 0 and dry_run:
            room_counts["inserted"] += 1
            continue
        partial = await insert_missing_by_slug(
            conn,
            table=rooms_table,
            rows=[room],
            update_existing=update_existing,
            dry_run=dry_run,
            extra_unique={"hotel_id": live_hotel_id},
        )
        for key in room_counts:
            room_counts[key] += partial[key]

    tour_counts = await insert_missing_by_slug(
        conn,
        table=tours_table,
        rows=load_seed_rows("tours.json"),
        update_existing=update_existing,
        dry_run=dry_run,
    )

    menu_rows = [
        row for row in load_seed_rows("menus.json") if row.get("url") in _MENU_URLS
    ]
    menu_counts = await insert_missing_menu_by_url(
        conn,
        table=menus_table,
        rows=menu_rows,
        update_existing=update_existing,
        dry_run=dry_run,
    )

    return {
        "hotels": hotel_counts,
        "hotel_rooms": room_counts,
        "tours": tour_counts,
        "menus": menu_counts,
    }
