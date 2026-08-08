"""Admin CRUD: districts."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, or_, select

from app.application.catalog import delete_guards as guards
from app.application.catalog.admin_list import paginate
from app.application.catalog.reorder import reorder_full_table
from app.core.deps import DbSession
from app.infrastructure.persistence.models import District
from app.presentation.api.v1.admin.deps import AdminUser, SameOrigin
from app.presentation.api.v1.admin.locations._shared import unique_slug
from app.presentation.schemas.admin_common import MessageOut, Paginated, ReorderRequest
from app.presentation.schemas.admin_locations import DistrictOut, DistrictWrite

router = APIRouter(prefix="/admin", tags=["admin-locations"])


@router.get("/districts", response_model=Paginated[DistrictOut])
async def list_districts(
    db: DbSession,
    _: AdminUser,
    page: int = 1,
    page_size: int = 25,
    q: str | None = None,
    province_id: int | None = None,
) -> Paginated[DistrictOut]:
    stmt = select(District).order_by(District.priority.desc(), District.name.asc())
    if q:
        stmt = stmt.where(or_(District.name.like(f"%{q}%"), District.slug.like(f"%{q}%")))
    if province_id is not None:
        stmt = stmt.where(District.province_id == province_id)
    items, total = await paginate(db, stmt, page=page, page_size=page_size)
    return Paginated(
        items=[DistrictOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/districts", response_model=DistrictOut, status_code=201)
async def create_district(
    body: DistrictWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> District:
    slug = body.slug or await unique_slug(db, District, body.name)
    if await db.scalar(select(func.count()).select_from(District).where(District.slug == slug)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Slug already exists")
    max_p = int(await db.scalar(select(func.coalesce(func.max(District.priority), 0))) or 0)
    row = District(
        province_id=body.province_id,
        district_type_id=body.district_type_id,
        name=body.name,
        slug=slug,
        title=body.title,
        description=body.description,
        thumbnail_url=body.thumbnail_url,
        image_list_url=body.image_list_url,
        content=body.content,
        priority=body.priority if body.priority is not None else max_p + 1,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.put("/districts/{item_id}", response_model=DistrictOut)
async def update_district(
    item_id: int, body: DistrictWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> District:
    row = await db.get(District, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    slug = body.slug or row.slug
    clash = await db.scalar(
        select(func.count())
        .select_from(District)
        .where(District.slug == slug, District.id != item_id)
    )
    if clash:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Slug already exists")
    row.province_id = body.province_id
    row.district_type_id = body.district_type_id
    row.name = body.name
    row.slug = slug
    row.title = body.title
    row.description = body.description
    row.thumbnail_url = body.thumbnail_url
    row.image_list_url = body.image_list_url
    row.content = body.content
    if body.priority is not None:
        row.priority = body.priority
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/districts/{item_id}", response_model=MessageOut)
async def delete_district(
    item_id: int, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    row = await db.get(District, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    try:
        await guards.delete_district(db, row)
    except guards.DeleteBlockedError as exc:
        guards.raise_http(exc)
    return MessageOut(message="Deleted")


@router.post("/districts/reorder", response_model=MessageOut)
async def reorder_districts(
    body: ReorderRequest, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    await reorder_full_table(db, District, body.ids)
    return MessageOut(message="Reordered")
