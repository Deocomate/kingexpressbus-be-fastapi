"""Admin CRUD: buses + bus_services."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, func, or_, select

from app.api.v1.admin.deps import AdminUser, SameOrigin
from app.core.deps import DbSession
from app.db.models import Bus, BusService
from app.db.models.fleet import bus_bus_service
from app.schemas.admin_fleet import BusOut, BusServiceOut, BusServiceWrite, BusWrite
from app.schemas.admin_common import MessageOut, Paginated, ReorderRequest
from app.services.admin_list import paginate
from app.services import delete_guards as guards
from app.services.reorder import reorder_full_table

router = APIRouter(prefix="/admin", tags=["admin-fleet"])


def _bus_out(bus: Bus, service_ids: list[int] | None = None) -> BusOut:
    ids = service_ids if service_ids is not None else [s.id for s in (bus.services or [])]
    return BusOut(
        id=bus.id,
        name=bus.name,
        model_name=bus.model_name,
        seat_count=bus.seat_count,
        thumbnail_url=bus.thumbnail_url,
        image_list_url=bus.image_list_url,
        content=bus.content,
        priority=bus.priority,
        service_ids=ids,
    )


async def _sync_services(db: DbSession, bus_id: int, service_ids: list[int]) -> None:
    await db.execute(delete(bus_bus_service).where(bus_bus_service.c.bus_id == bus_id))
    for sid in service_ids:
        await db.execute(
            bus_bus_service.insert().values(bus_id=bus_id, bus_service_id=sid)
        )


# ── Bus services ───────────────────────────────────────────────────────────
@router.get("/bus-services", response_model=Paginated[BusServiceOut])
async def list_bus_services(
    db: DbSession, _: AdminUser, page: int = 1, page_size: int = 25, q: str | None = None
) -> Paginated[BusServiceOut]:
    stmt = select(BusService).order_by(BusService.priority.desc(), BusService.name.asc())
    if q:
        stmt = stmt.where(BusService.name.like(f"%{q}%"))
    items, total = await paginate(db, stmt, page=page, page_size=page_size)
    return Paginated(
        items=[BusServiceOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/bus-services", response_model=BusServiceOut, status_code=201)
async def create_bus_service(
    body: BusServiceWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> BusService:
    max_p = int(await db.scalar(select(func.coalesce(func.max(BusService.priority), 0))) or 0)
    row = BusService(
        name=body.name,
        icon=body.icon,
        priority=body.priority if body.priority is not None else max_p + 1,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.put("/bus-services/{item_id}", response_model=BusServiceOut)
async def update_bus_service(
    item_id: int, body: BusServiceWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> BusService:
    row = await db.get(BusService, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    row.name = body.name
    row.icon = body.icon
    if body.priority is not None:
        row.priority = body.priority
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/bus-services/{item_id}", response_model=MessageOut)
async def delete_bus_service(
    item_id: int, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    row = await db.get(BusService, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    await db.execute(delete(bus_bus_service).where(bus_bus_service.c.bus_service_id == item_id))
    await db.delete(row)
    await db.commit()
    return MessageOut(message="Deleted")


# ── Buses ──────────────────────────────────────────────────────────────────
@router.get("/buses", response_model=Paginated[BusOut])
async def list_buses(
    db: DbSession, _: AdminUser, page: int = 1, page_size: int = 25, q: str | None = None
) -> Paginated[BusOut]:
    stmt = select(Bus).order_by(Bus.priority.desc(), Bus.name.asc())
    if q:
        stmt = stmt.where(or_(Bus.name.like(f"%{q}%"), Bus.model_name.like(f"%{q}%")))
    items, total = await paginate(db, stmt, page=page, page_size=page_size)
    return Paginated(
        items=[_bus_out(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/buses", response_model=BusOut, status_code=201)
async def create_bus(
    body: BusWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> BusOut:
    max_p = int(await db.scalar(select(func.coalesce(func.max(Bus.priority), 0))) or 0)
    row = Bus(
        name=body.name,
        model_name=body.model_name,
        seat_count=body.seat_count,
        thumbnail_url=body.thumbnail_url,
        image_list_url=body.image_list_url,
        content=body.content,
        priority=body.priority if body.priority is not None else max_p + 1,
    )
    db.add(row)
    await db.flush()
    await _sync_services(db, row.id, body.service_ids)
    await db.commit()
    await db.refresh(row)
    return _bus_out(row, body.service_ids)


@router.get("/buses/{item_id}", response_model=BusOut)
async def get_bus(item_id: int, db: DbSession, _: AdminUser) -> BusOut:
    row = await db.get(Bus, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    return _bus_out(row)


@router.put("/buses/{item_id}", response_model=BusOut)
async def update_bus(
    item_id: int, body: BusWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> BusOut:
    row = await db.get(Bus, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    row.name = body.name
    row.model_name = body.model_name
    row.seat_count = body.seat_count
    row.thumbnail_url = body.thumbnail_url
    row.image_list_url = body.image_list_url
    row.content = body.content
    if body.priority is not None:
        row.priority = body.priority
    await _sync_services(db, row.id, body.service_ids)
    await db.commit()
    await db.refresh(row)
    return _bus_out(row, body.service_ids)


@router.delete("/buses/{item_id}", response_model=MessageOut)
async def delete_bus(item_id: int, db: DbSession, _: AdminUser, __: SameOrigin) -> MessageOut:
    row = await db.get(Bus, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    try:
        await guards.delete_bus(db, row)
    except guards.DeleteBlockedError as exc:
        guards.raise_http(exc)
    return MessageOut(message="Deleted")


@router.post("/buses/reorder", response_model=MessageOut)
async def reorder_buses(
    body: ReorderRequest, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    await reorder_full_table(db, Bus, body.ids)
    return MessageOut(message="Reordered")
