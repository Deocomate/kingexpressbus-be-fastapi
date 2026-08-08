"""Shared helpers for additive seed updates."""

from __future__ import annotations

import json
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from sqlalchemy import Date, DateTime, Table, Time, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

SEED_DATA_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "app"
    / "infrastructure"
    / "persistence"
    / "seed_data"
)


def load_seed_rows(filename: str) -> list[dict[str, Any]]:
    path = SEED_DATA_DIR / filename
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise TypeError(f"{path} must contain a JSON array of row objects")
    return [dict(row) for row in data]


def strip_primary_key(row: dict[str, Any], *, pk: str = "id") -> dict[str, Any]:
    out = dict(row)
    out.pop(pk, None)
    return out


def coerce_row_types(table: Table, row: dict[str, Any]) -> dict[str, Any]:
    """Convert JSON string date/time/datetime values to native Python types."""
    date_cols = {
        c.name
        for c in table.columns
        if isinstance(c.type, Date) and not isinstance(c.type, DateTime)
    }
    datetime_cols = {c.name for c in table.columns if isinstance(c.type, DateTime)}
    time_cols = {c.name for c in table.columns if isinstance(c.type, Time)}

    out = dict(row)
    for col in date_cols:
        if isinstance(out.get(col), str):
            out[col] = date.fromisoformat(out[col])
    for col in datetime_cols:
        if isinstance(out.get(col), str):
            out[col] = datetime.strptime(out[col], "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
    for col in time_cols:
        if isinstance(out.get(col), str):
            out[col] = time.fromisoformat(out[col])
    return out


async def fetch_scalar(
    conn: AsyncConnection, stmt: Any
) -> Any:
    result = await conn.execute(stmt)
    return result.scalar_one_or_none()


async def insert_missing_by_slug(
    conn: AsyncConnection,
    *,
    table: Table,
    rows: list[dict[str, Any]],
    update_existing: bool,
    dry_run: bool,
    extra_unique: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Insert rows keyed by ``slug`` (and optional extra equality filters).

    Returns counts: inserted / updated / skipped.
    """
    counts = {"inserted": 0, "updated": 0, "skipped": 0}
    for raw in rows:
        slug = raw["slug"]
        payload = coerce_row_types(table, strip_primary_key(raw))
        where = [table.c.slug == slug]
        if extra_unique:
            for col, value in extra_unique.items():
                where.append(table.c[col] == value)
                payload[col] = value

        existing_id = await fetch_scalar(
            conn, select(table.c.id).where(*where).limit(1)
        )
        if existing_id is None:
            counts["inserted"] += 1
            if not dry_run:
                await conn.execute(insert(table).values(**payload))
            continue

        if update_existing:
            counts["updated"] += 1
            if not dry_run:
                await conn.execute(
                    update(table).where(table.c.id == existing_id).values(**payload)
                )
        else:
            counts["skipped"] += 1
    return counts


async def insert_missing_menu_by_url(
    conn: AsyncConnection,
    *,
    table: Table,
    rows: list[dict[str, Any]],
    update_existing: bool,
    dry_run: bool,
) -> dict[str, int]:
    counts = {"inserted": 0, "updated": 0, "skipped": 0}
    for raw in rows:
        url = raw["url"]
        payload = coerce_row_types(table, strip_primary_key(raw))
        existing_id = await fetch_scalar(
            conn, select(table.c.id).where(table.c.url == url).limit(1)
        )
        if existing_id is None:
            counts["inserted"] += 1
            if not dry_run:
                await conn.execute(insert(table).values(**payload))
            continue
        if update_existing:
            counts["updated"] += 1
            if not dry_run:
                await conn.execute(
                    update(table).where(table.c.id == existing_id).values(**payload)
                )
        else:
            counts["skipped"] += 1
    return counts
