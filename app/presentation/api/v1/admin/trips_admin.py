"""Admin CRUD: trips + trip_blocks."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.application.catalog import delete_guards as guards
from app.application.catalog.admin_list import paginate
from app.core.deps import DbSession
from app.infrastructure.persistence.models import Bus, Province, Route, Trip, TripBlock
from app.presentation.api.v1.admin.deps import AdminUser, SameOrigin
from app.presentation.schemas.admin_common import MessageOut, Paginated
from app.presentation.schemas.admin_trips import (
    TripBlockOut,
    TripBlockWrite,
    TripOut,
    TripWrite,
)

router = APIRouter(prefix="/admin", tags=["admin-trips"])


def _trip_out(
    trip: Trip,
    *,
    route_name: str | None = None,
    province_start_id: int | None = None,
    province_start_name: str | None = None,
    province_end_id: int | None = None,
    province_end_name: str | None = None,
    bus_name: str | None = None,
) -> TripOut:
    out = TripOut.model_validate(trip)
    out.route_name = route_name
    out.province_start_id = province_start_id
    out.province_start_name = province_start_name
    out.province_end_id = province_end_id
    out.province_end_name = province_end_name
    out.bus_name = bus_name
    return out


@router.get("/trips", response_model=Paginated[TripOut])
async def list_trips(
    db: DbSession,
    _: AdminUser,
    page: int = 1,
    page_size: int = 25,
    route_id: int | None = None,
    bus_id: int | None = None,
    province_id: int | None = None,
    province_start_id: int | None = None,
    province_end_id: int | None = None,
) -> Paginated[TripOut]:
    # province_id kept as alias for province_start_id (older clients).
    start_id = province_start_id if province_start_id is not None else province_id
    province_start = aliased(Province)
    province_end = aliased(Province)
    stmt = (
        select(
            Trip,
            Route.name,
            Route.province_start_id,
            province_start.name,
            Route.province_end_id,
            province_end.name,
            Bus.name,
        )
        .join(Route, Trip.route_id == Route.id)
        .join(province_start, Route.province_start_id == province_start.id)
        .join(province_end, Route.province_end_id == province_end.id)
        .join(Bus, Trip.bus_id == Bus.id)
        .order_by(
            Route.province_start_id.asc(),
            Route.province_end_id.asc(),
            Trip.start_time.asc(),
            Trip.priority.desc(),
        )
    )
    if route_id is not None:
        stmt = stmt.where(Trip.route_id == route_id)
    if bus_id is not None:
        stmt = stmt.where(Trip.bus_id == bus_id)
    if start_id is not None:
        stmt = stmt.where(Route.province_start_id == start_id)
    if province_end_id is not None:
        stmt = stmt.where(Route.province_end_id == province_end_id)
    rows, total = await paginate(db, stmt, page=page, page_size=page_size, as_rows=True)
    items = [
        _trip_out(
            trip,
            route_name=route_name,
            province_start_id=start_pid,
            province_start_name=start_name,
            province_end_id=end_pid,
            province_end_name=end_name,
            bus_name=bus_name,
        )
        for trip, route_name, start_pid, start_name, end_pid, end_name, bus_name in rows
    ]
    return Paginated(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/trips", response_model=TripOut, status_code=201)
async def create_trip(
    body: TripWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> Trip:
    max_p = int(await db.scalar(select(func.coalesce(func.max(Trip.priority), 0))) or 0)
    row = Trip(
        bus_id=body.bus_id,
        route_id=body.route_id,
        start_time=body.start_time,
        end_time=body.end_time,
        price=body.price,
        is_active=body.is_active,
        priority=body.priority if body.priority is not None else max_p + 1,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/trips/{item_id}", response_model=TripOut)
async def get_trip(item_id: int, db: DbSession, _: AdminUser) -> Trip:
    row = await db.get(Trip, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    return row


@router.put("/trips/{item_id}", response_model=TripOut)
async def update_trip(
    item_id: int, body: TripWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> Trip:
    row = await db.get(Trip, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    row.bus_id = body.bus_id
    row.route_id = body.route_id
    row.start_time = body.start_time
    row.end_time = body.end_time
    row.price = body.price
    row.is_active = body.is_active
    if body.priority is not None:
        row.priority = body.priority
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/trips/{item_id}", response_model=MessageOut)
async def delete_trip(item_id: int, db: DbSession, _: AdminUser, __: SameOrigin) -> MessageOut:
    row = await db.get(Trip, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    try:
        await guards.delete_trip(db, row)
    except guards.DeleteBlockedError as exc:
        guards.raise_http(exc)
    return MessageOut(message="Deleted")


# ── Trip blocks ────────────────────────────────────────────────────────────
@router.get("/trip-blocks", response_model=Paginated[TripBlockOut])
async def list_trip_blocks(
    db: DbSession,
    _: AdminUser,
    page: int = 1,
    page_size: int = 25,
    trip_id: int | None = None,
) -> Paginated[TripBlockOut]:
    stmt = select(TripBlock).order_by(TripBlock.start_date.desc())
    if trip_id is not None:
        stmt = stmt.where(TripBlock.trip_id == trip_id)
    items, total = await paginate(db, stmt, page=page, page_size=page_size)
    return Paginated(
        items=[TripBlockOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/trip-blocks", response_model=TripBlockOut, status_code=201)
async def create_trip_block(
    body: TripBlockWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> TripBlock:
    if body.block_type not in ("off_day", "sold_out"):
        raise HTTPException(422, detail="block_type must be off_day or sold_out")
    if body.end_date < body.start_date:
        raise HTTPException(422, detail="end_date must be >= start_date")
    row = TripBlock(
        trip_id=body.trip_id,
        start_date=body.start_date,
        end_date=body.end_date,
        block_type=body.block_type,
        note=body.note,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.put("/trip-blocks/{item_id}", response_model=TripBlockOut)
async def update_trip_block(
    item_id: int, body: TripBlockWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> TripBlock:
    row = await db.get(TripBlock, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    row.trip_id = body.trip_id
    row.start_date = body.start_date
    row.end_date = body.end_date
    row.block_type = body.block_type
    row.note = body.note
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/trip-blocks/{item_id}", response_model=MessageOut)
async def delete_trip_block(
    item_id: int, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    row = await db.get(TripBlock, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    await db.delete(row)
    await db.commit()
    return MessageOut(message="Deleted")
