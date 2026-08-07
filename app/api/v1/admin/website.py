"""Admin website profile + menu tree CRUD (max depth 4)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select, update

from app.api.v1.admin.deps import AdminUser, SameOrigin
from app.core.deps import DbSession
from app.db.models import Menu, WebProfile
from app.schemas.admin_website import (
    MenuOut,
    MenuTreeReorderRequest,
    MenuWrite,
    WebProfileAdminOut,
    WebProfileWrite,
)
from app.schemas.admin_common import MessageOut, Paginated
from app.services.admin_list import paginate

router = APIRouter(prefix="/admin", tags=["admin-website"])

ROOT_PARENT = -1
MAX_DEPTH = 4


async def _menu_depth(db: DbSession, parent_id: int | None) -> int:
    """Depth of a new node under parent_id (root children = depth 1)."""
    if parent_id is None or parent_id == ROOT_PARENT:
        return 1
    depth = 1
    current = parent_id
    seen: set[int] = set()
    while current is not None and current != ROOT_PARENT:
        if current in seen:
            break
        seen.add(current)
        depth += 1
        if depth > MAX_DEPTH:
            return depth
        row = await db.get(Menu, current)
        if row is None:
            break
        current = row.parent_id if row.parent_id is not None else ROOT_PARENT
    return depth


@router.get("/web-profiles", response_model=list[WebProfileAdminOut])
async def list_web_profiles(db: DbSession, _: AdminUser) -> list[WebProfile]:
    result = await db.execute(select(WebProfile).order_by(WebProfile.id.asc()))
    return list(result.scalars().all())


@router.get("/web-profiles/{item_id}", response_model=WebProfileAdminOut)
async def get_web_profile(item_id: int, db: DbSession, _: AdminUser) -> WebProfile:
    row = await db.get(WebProfile, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    return row


@router.put("/web-profiles/{item_id}", response_model=WebProfileAdminOut)
async def update_web_profile(
    item_id: int, body: WebProfileWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> WebProfile:
    row = await db.get(WebProfile, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    data = body.model_dump(exclude_unset=True)
    if data.get("is_default") is True:
        await db.execute(update(WebProfile).values(is_default=False))
    for key, value in data.items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return row


# ── Menus ──────────────────────────────────────────────────────────────────
@router.get("/menus", response_model=list[MenuOut])
async def list_menus(db: DbSession, _: AdminUser) -> list[Menu]:
    result = await db.execute(select(Menu).order_by(Menu.priority.desc(), Menu.id.asc()))
    return list(result.scalars().all())


@router.post("/menus", response_model=MenuOut, status_code=201)
async def create_menu(
    body: MenuWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> Menu:
    parent_id = body.parent_id if body.parent_id is not None else ROOT_PARENT
    depth = await _menu_depth(db, parent_id)
    if depth > MAX_DEPTH:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Menu depth cannot exceed {MAX_DEPTH}",
        )
    max_p = int(await db.scalar(select(func.coalesce(func.max(Menu.priority), 0))) or 0)
    row = Menu(
        name=body.name,
        url=body.url,
        parent_id=parent_id,
        priority=body.priority if body.priority is not None else max_p + 1,
        type=body.type,
        related_id=body.related_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.put("/menus/{item_id}", response_model=MenuOut)
async def update_menu(
    item_id: int, body: MenuWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> Menu:
    row = await db.get(Menu, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    parent_id = body.parent_id if body.parent_id is not None else ROOT_PARENT
    if parent_id == item_id:
        raise HTTPException(422, detail="Menu cannot be its own parent")
    depth = await _menu_depth(db, parent_id)
    if depth > MAX_DEPTH:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Menu depth cannot exceed {MAX_DEPTH}",
        )
    row.name = body.name
    row.url = body.url
    row.parent_id = parent_id
    row.type = body.type
    row.related_id = body.related_id
    if body.priority is not None:
        row.priority = body.priority
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/menus/{item_id}", response_model=MessageOut)
async def delete_menu(item_id: int, db: DbSession, _: AdminUser, __: SameOrigin) -> MessageOut:
    row = await db.get(Menu, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    children = int(
        await db.scalar(select(func.count()).select_from(Menu).where(Menu.parent_id == item_id))
        or 0
    )
    if children:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"message": f"Không thể xóa: còn {children} menu con.", "booking_count": 0},
        )
    await db.delete(row)
    await db.commit()
    return MessageOut(message="Deleted")


@router.post("/menus/reorder-tree", response_model=MessageOut)
async def reorder_menu_tree(
    body: MenuTreeReorderRequest, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    ids = [i.id for i in body.items]
    total = int(await db.scalar(select(func.count()).select_from(Menu)) or 0)
    if len(ids) != len(set(ids)) or len(ids) != total:
        raise HTTPException(422, detail="Danh sách sắp xếp không khớp toàn bộ bảng.")
    for item in body.items:
        parent = item.parent_id if item.parent_id is not None else ROOT_PARENT
        depth = await _menu_depth(db, parent)
        if depth > MAX_DEPTH:
            raise HTTPException(422, detail=f"Menu depth cannot exceed {MAX_DEPTH}")
        await db.execute(
            update(Menu)
            .where(Menu.id == item.id)
            .values(parent_id=parent, priority=item.priority)
        )
    await db.commit()
    return MessageOut(message="Reordered")
