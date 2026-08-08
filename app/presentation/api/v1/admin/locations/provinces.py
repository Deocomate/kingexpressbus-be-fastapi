"""Admin CRUD: provinces."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, or_, select

from app.application.catalog import delete_guards as guards
from app.application.catalog.admin_list import paginate
from app.application.catalog.reorder import reorder_full_table
from app.core.deps import DbSession
from app.infrastructure.persistence.models import Province
from app.presentation.api.v1.admin.deps import AdminUser, SameOrigin
from app.presentation.api.v1.admin.locations._shared import unique_slug
from app.presentation.schemas.admin_common import MessageOut, Paginated, ReorderRequest
from app.presentation.schemas.admin_locations import ProvinceOut, ProvinceWrite

router = APIRouter(prefix="/admin", tags=["admin-locations"])


@router.get("/provinces", response_model=Paginated[ProvinceOut])
async def list_provinces(
    db: DbSession,
    _: AdminUser,
    page: int = 1,
    page_size: int = 25,
    q: str | None = None,
) -> Paginated[ProvinceOut]:
    stmt = select(Province).order_by(Province.priority.desc(), Province.name.asc())
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Province.name.like(like), Province.slug.like(like)))
    items, total = await paginate(db, stmt, page=page, page_size=page_size)
    return Paginated(
        items=[ProvinceOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/provinces", response_model=ProvinceOut, status_code=201)
async def create_province(
    body: ProvinceWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> Province:
    slug = body.slug or await unique_slug(db, Province, body.name)
    if await db.scalar(select(func.count()).select_from(Province).where(Province.slug == slug)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Slug already exists")
    max_p = int(await db.scalar(select(func.coalesce(func.max(Province.priority), 0))) or 0)
    row = Province(
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


@router.get("/provinces/{province_id}", response_model=ProvinceOut)
async def get_province(province_id: int, db: DbSession, _: AdminUser) -> Province:
    row = await db.get(Province, province_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    return row


@router.put("/provinces/{province_id}", response_model=ProvinceOut)
async def update_province(
    province_id: int, body: ProvinceWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> Province:
    row = await db.get(Province, province_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    slug = body.slug or row.slug
    clash = await db.scalar(
        select(func.count())
        .select_from(Province)
        .where(Province.slug == slug, Province.id != province_id)
    )
    if clash:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Slug already exists")
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


@router.delete("/provinces/{province_id}", response_model=MessageOut)
async def delete_province(
    province_id: int, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    row = await db.get(Province, province_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    try:
        await guards.delete_province(db, row)
    except guards.DeleteBlockedError as exc:
        guards.raise_http(exc)
    return MessageOut(message="Deleted")


@router.post("/provinces/reorder", response_model=MessageOut)
async def reorder_provinces(
    body: ReorderRequest, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    await reorder_full_table(db, Province, body.ids)
    return MessageOut(message="Reordered")
