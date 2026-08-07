"""Admin CRUD: stops."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, or_, select

from app.api.v1.admin.deps import AdminUser, SameOrigin
from app.core.deps import DbSession
from app.db.models import District, Province, Stop
from app.schemas.admin_common import MessageOut, Paginated, ReorderRequest
from app.schemas.admin_locations import StopOut, StopWrite
from app.services import delete_guards as guards
from app.services.admin_list import paginate
from app.services.reorder import reorder_full_table

router = APIRouter(prefix="/admin", tags=["admin-locations"])


def _stop_out(
    stop: Stop,
    *,
    province_id: int | None = None,
    province_name: str | None = None,
    district_name: str | None = None,
) -> StopOut:
    out = StopOut.model_validate(stop)
    out.province_id = province_id
    out.province_name = province_name
    out.district_name = district_name
    return out


@router.get("/stops", response_model=Paginated[StopOut])
async def list_stops(
    db: DbSession,
    _: AdminUser,
    page: int = 1,
    page_size: int = 25,
    q: str | None = None,
    district_id: int | None = None,
    province_id: int | None = None,
) -> Paginated[StopOut]:
    stmt = (
        select(
            Stop,
            District.name.label("district_name"),
            Province.id.label("province_id"),
            Province.name.label("province_name"),
        )
        .join(District, Stop.district_id == District.id)
        .join(Province, District.province_id == Province.id)
        .order_by(Province.name.asc(), Stop.priority.desc(), Stop.name.asc())
    )
    if q:
        stmt = stmt.where(or_(Stop.name.like(f"%{q}%"), Stop.address.like(f"%{q}%")))
    if district_id is not None:
        stmt = stmt.where(Stop.district_id == district_id)
    if province_id is not None:
        stmt = stmt.where(Province.id == province_id)
    rows, total = await paginate(db, stmt, page=page, page_size=page_size)
    items = []
    for row in rows:
        # row may be Stop ORM or Row tuple
        if hasattr(row, "district_name"):
            stop, district_name, prov_id, province_name = row
            items.append(
                _stop_out(
                    stop,
                    province_id=prov_id,
                    province_name=province_name,
                    district_name=district_name,
                )
            )
        else:
            items.append(StopOut.model_validate(row))
    return Paginated(items=items, total=total, page=page, page_size=page_size)


@router.post("/stops", response_model=StopOut, status_code=201)
async def create_stop(
    body: StopWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> StopOut:
    max_p = int(await db.scalar(select(func.coalesce(func.max(Stop.priority), 0))) or 0)
    row = Stop(
        district_id=body.district_id,
        name=body.name,
        address=body.address,
        priority=body.priority if body.priority is not None else max_p + 1,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return StopOut.model_validate(row)


@router.put("/stops/{item_id}", response_model=StopOut)
async def update_stop(
    item_id: int, body: StopWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> StopOut:
    row = await db.get(Stop, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    row.district_id = body.district_id
    row.name = body.name
    row.address = body.address
    if body.priority is not None:
        row.priority = body.priority
    await db.commit()
    await db.refresh(row)
    return StopOut.model_validate(row)


@router.delete("/stops/{item_id}", response_model=MessageOut)
async def delete_stop(item_id: int, db: DbSession, _: AdminUser, __: SameOrigin) -> MessageOut:
    row = await db.get(Stop, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    try:
        await guards.delete_stop(db, row)
    except guards.DeleteBlockedError as exc:
        guards.raise_http(exc)
    return MessageOut(message="Deleted")


@router.post("/stops/reorder", response_model=MessageOut)
async def reorder_stops(
    body: ReorderRequest, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    await reorder_full_table(db, Stop, body.ids)
    return MessageOut(message="Reordered")
