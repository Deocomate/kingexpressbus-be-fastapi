"""Admin CRUD: district types."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.application.catalog.admin_list import paginate
from app.application.catalog.reorder import reorder_full_table
from app.core.deps import DbSession
from app.infrastructure.persistence.models import District, DistrictType
from app.presentation.api.v1.admin.deps import AdminUser, SameOrigin
from app.presentation.schemas.admin_common import MessageOut, Paginated, ReorderRequest
from app.presentation.schemas.admin_locations import DistrictTypeOut, DistrictTypeWrite

router = APIRouter(prefix="/admin", tags=["admin-locations"])


@router.get("/district-types", response_model=Paginated[DistrictTypeOut])
async def list_district_types(
    db: DbSession, _: AdminUser, page: int = 1, page_size: int = 25, q: str | None = None
) -> Paginated[DistrictTypeOut]:
    stmt = select(DistrictType).order_by(DistrictType.priority.desc(), DistrictType.name.asc())
    if q:
        stmt = stmt.where(DistrictType.name.like(f"%{q}%"))
    items, total = await paginate(db, stmt, page=page, page_size=page_size)
    return Paginated(
        items=[DistrictTypeOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/district-types", response_model=DistrictTypeOut, status_code=201)
async def create_district_type(
    body: DistrictTypeWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> DistrictType:
    max_p = int(await db.scalar(select(func.coalesce(func.max(DistrictType.priority), 0))) or 0)
    row = DistrictType(
        name=body.name,
        priority=body.priority if body.priority is not None else max_p + 1,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.put("/district-types/{item_id}", response_model=DistrictTypeOut)
async def update_district_type(
    item_id: int, body: DistrictTypeWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> DistrictType:
    row = await db.get(DistrictType, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    row.name = body.name
    if body.priority is not None:
        row.priority = body.priority
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/district-types/{item_id}", response_model=MessageOut)
async def delete_district_type(
    item_id: int, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    row = await db.get(DistrictType, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    deps = int(
        await db.scalar(
            select(func.count()).select_from(District).where(District.district_type_id == item_id)
        )
        or 0
    )
    if deps:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"message": f"Không thể xóa: còn {deps} địa điểm liên quan.", "booking_count": 0},
        )
    await db.delete(row)
    await db.commit()
    return MessageOut(message="Deleted")


@router.post("/district-types/reorder", response_model=MessageOut)
async def reorder_district_types(
    body: ReorderRequest, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    await reorder_full_table(db, DistrictType, body.ids)
    return MessageOut(message="Reordered")
