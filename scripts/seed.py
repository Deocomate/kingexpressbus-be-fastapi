"""CLI seeder — truncates business tables and bulk-inserts the production
dataset from app/db/seed_data/*.json.

Usage:
    python scripts/seed.py            # refuses if settings look like production
    python scripts/seed.py --force    # required if pointed at anything that
                                       # looks like production

Truncate + insert order is FK-safe (parents before children). Re-running is
safe: every table is truncated before it is re-seeded, so there are no
duplicate-key errors.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from sqlalchemy import Date, DateTime, Table, Time, insert, text
from sqlalchemy.ext.asyncio import AsyncConnection

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models.fleet import Bus, BusService, bus_bus_service
from app.db.models.location import District, DistrictType, Province, Stop
from app.db.models.ops import Route, RouteStop, Trip
from app.db.models.surcharge import HolidaySurcharge, HolidaySurchargeRoute
from app.db.models.user import User
from app.db.models.website import Menu, WebProfile
from app.db.session import engine

SEED_DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "db" / "seed_data"

ADMIN_PASSWORD_SENTINEL = "__HASH_ADMIN_PASSWORD__"
ADMIN_PLAINTEXT_PASSWORD = "Admin@123"

PRODUCTION_ENV_MARKERS = {"production", "prod"}

# (table name, ORM model / Core Table, seed json filename) — FK-safe:
# parents before children.
SEED_STEPS: list[tuple[str, Any, str]] = [
    ("users", User, "users.json"),
    ("web_profiles", WebProfile, "web_profiles.json"),
    ("provinces", Province, "provinces.json"),
    ("district_types", DistrictType, "district_types.json"),
    ("bus_services", BusService, "bus_services.json"),
    ("buses", Bus, "buses.json"),
    ("bus_bus_service", bus_bus_service, "bus_bus_service.json"),
    ("holiday_surcharges", HolidaySurcharge, "holiday_surcharges.json"),
    ("districts", District, "districts.json"),
    ("stops", Stop, "stops.json"),
    ("routes", Route, "routes.json"),
    ("route_stops", RouteStop, "route_stops.json"),
    ("trips", Trip, "trips.json"),
    ("holiday_surcharge_routes", HolidaySurchargeRoute, "holiday_surcharge_routes.json"),
    ("menus", Menu, "menus.json"),
]

# Reverse dependency order for truncate (children before parents).
# `bookings` has no seed data but is truncated because it FKs into
# users/trips/stops.
TRUNCATE_TABLES = [
    "bookings",
    "menus",
    "trips",
    "route_stops",
    "holiday_surcharge_routes",
    "routes",
    "stops",
    "districts",
    "holiday_surcharges",
    "bus_bus_service",
    "buses",
    "bus_services",
    "district_types",
    "provinces",
    "web_profiles",
    "users",
]


def load_rows(filename: str) -> list[dict[str, Any]]:
    """Load and validate one seed_data/*.json file (list of row dicts)."""
    path = SEED_DATA_DIR / filename
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise TypeError(f"{path} must contain a JSON array of row objects")
    for row in data:
        if not isinstance(row, dict):
            raise TypeError(f"{path} contains a non-object row: {row!r}")
    return data


def prepare_user_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hash the admin sentinel password fresh; other users keep their
    existing bcrypt hashes verbatim.

    Guest rows may have password=null (column is nullable). Leave them as-is.
    """
    prepared = []
    for row in rows:
        row = dict(row)
        if row.get("password") == ADMIN_PASSWORD_SENTINEL:
            row["password"] = hash_password(ADMIN_PLAINTEXT_PASSWORD)
        prepared.append(row)
    return prepared


def coerce_row_types(table: Table, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert JSON string date/time/datetime values to native Python
    objects matching each column's SQLAlchemy type, so the DBAPI receives
    correctly typed bind parameters instead of raw strings."""
    date_cols = {c.name for c in table.columns if isinstance(c.type, Date) and not isinstance(c.type, DateTime)}
    datetime_cols = {c.name for c in table.columns if isinstance(c.type, DateTime)}
    time_cols = {c.name for c in table.columns if isinstance(c.type, Time)}

    coerced = []
    for row in rows:
        row = dict(row)
        for col in date_cols:
            if isinstance(row.get(col), str):
                row[col] = date.fromisoformat(row[col])
        for col in datetime_cols:
            if isinstance(row.get(col), str):
                # Naive datetime by design: matches the DB columns' naive
                # DateTime type (MySQL DATETIME has no tz, see app/db/base.py).
                row[col] = datetime.strptime(row[col], "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
        for col in time_cols:
            if isinstance(row.get(col), str):
                row[col] = time.fromisoformat(row[col])
        coerced.append(row)
    return coerced


def looks_like_production(app_env: str) -> bool:
    return app_env.strip().lower() in PRODUCTION_ENV_MARKERS


async def truncate_all(conn: AsyncConnection) -> None:
    await conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    try:
        for table_name in TRUNCATE_TABLES:
            await conn.execute(text(f"TRUNCATE TABLE `{table_name}`"))
    finally:
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))


async def seed_all(conn: AsyncConnection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table_name, target, filename in SEED_STEPS:
        rows = load_rows(filename)
        if table_name == "users":
            rows = prepare_user_rows(rows)
        table = target if isinstance(target, Table) else target.__table__
        rows = coerce_row_types(table, rows)
        counts[table_name] = len(rows)
        if rows:
            await conn.execute(insert(table), rows)
    return counts


async def run(force: bool) -> int:
    settings = get_settings()

    if looks_like_production(settings.app_env) and not force:
        print(
            f"Refusing to seed: APP_ENV={settings.app_env!r} looks like production. "
            "Pass --force to override.",
            file=sys.stderr,
        )
        return 1

    try:
        async with engine.begin() as conn:
            await truncate_all(conn)
            counts = await seed_all(conn)
    finally:
        await engine.dispose()

    print("Seed complete:")
    for table_name, count in counts.items():
        print(f"  {table_name}: {count}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the database with the production content from app/db/seed_data/."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Required if settings.app_env looks like production.",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.force)))


if __name__ == "__main__":
    main()
