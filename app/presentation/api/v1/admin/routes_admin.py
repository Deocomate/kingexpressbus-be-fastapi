"""Admin CRUD: routes + route_stops."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import aliased

from app.application.catalog import delete_guards as guards
from app.application.catalog.admin_list import paginate, slugify
from app.application.catalog.reorder import reorder_full_table, reorder_scoped
from app.core.deps import DbSession
from app.infrastructure.persistence.models import Province, Route, RouteStop, Stop
from app.presentation.api.v1.admin.deps import AdminUser, SameOrigin
from app.presentation.schemas.admin_common import MessageOut, Paginated, ReorderRequest
from app.presentation.schemas.admin_routes import (
    RouteOut,
    RouteStopOut,
    RouteStopWrite,
    RouteWrite,
)

router = APIRouter(prefix="/admin", tags=["admin-routes"])


def _route_out(
    row: Route,
    *,
    province_start_name: str | None = None,
    province_end_name: str | None = None,
) -> RouteOut:
    out = RouteOut.model_validate(row)
    out.province_start_name = province_start_name
    out.province_end_name = province_end_name
    return out


def _route_stop_out(
    row: RouteStop,
    *,
    stop_name: str | None = None,
    stop_address: str | None = None,
) -> RouteStopOut:
    out = RouteStopOut.model_validate(row)
    out.stop_name = stop_name
    out.stop_address = stop_address
    return out


@router.get("/routes", response_model=Paginated[RouteOut])
async def list_routes(
    db: DbSession,
    _: AdminUser,
    page: int = 1,
    page_size: int = 25,
    q: str | None = None,
    province_start_id: int | None = None,
    province_end_id: int | None = None,
) -> Paginated[RouteOut]:
    province_start = aliased(Province)
    province_end = aliased(Province)
    stmt = (
        select(Route, province_start.name, province_end.name)
        .join(province_start, Route.province_start_id == province_start.id)
        .join(province_end, Route.province_end_id == province_end.id)
        .order_by(
            Route.province_start_id.asc(),
            Route.priority.desc(),
            Route.name.asc(),
        )
    )
    if q:
        stmt = stmt.where(or_(Route.name.like(f"%{q}%"), Route.slug.like(f"%{q}%")))
    if province_start_id is not None:
        stmt = stmt.where(Route.province_start_id == province_start_id)
    if province_end_id is not None:
        stmt = stmt.where(Route.province_end_id == province_end_id)
    rows, total = await paginate(db, stmt, page=page, page_size=page_size, as_rows=True)
    items = [
        _route_out(route, province_start_name=start_name, province_end_name=end_name)
        for route, start_name, end_name in rows
    ]
    return Paginated(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/routes", response_model=RouteOut, status_code=201)
async def create_route(
    body: RouteWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> Route:
    slug = body.slug or slugify(body.name)
    if await db.scalar(select(func.count()).select_from(Route).where(Route.slug == slug)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Slug already exists")
    max_p = int(await db.scalar(select(func.coalesce(func.max(Route.priority), 0))) or 0)
    row = Route(
        province_start_id=body.province_start_id,
        province_end_id=body.province_end_id,
        name=body.name,
        slug=slug,
        title=body.title,
        description=body.description,
        duration=body.duration,
        distance_km=body.distance_km,
        price_default=body.price_default,
        thumbnail_url=body.thumbnail_url,
        image_list_url=body.image_list_url,
        content=body.content,
        available_hotel_pickup=body.available_hotel_pickup,
        priority=body.priority if body.priority is not None else max_p + 1,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/routes/{item_id}", response_model=RouteOut)
async def get_route(item_id: int, db: DbSession, _: AdminUser) -> Route:
    row = await db.get(Route, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    return row


@router.put("/routes/{item_id}", response_model=RouteOut)
async def update_route(
    item_id: int, body: RouteWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> Route:
    row = await db.get(Route, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    slug = body.slug or row.slug
    clash = await db.scalar(
        select(func.count()).select_from(Route).where(Route.slug == slug, Route.id != item_id)
    )
    if clash:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Slug already exists")
    for field in (
        "province_start_id",
        "province_end_id",
        "name",
        "title",
        "description",
        "duration",
        "distance_km",
        "price_default",
        "thumbnail_url",
        "image_list_url",
        "content",
        "available_hotel_pickup",
    ):
        setattr(row, field, getattr(body, field))
    row.slug = slug
    if body.priority is not None:
        row.priority = body.priority
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/routes/{item_id}", response_model=MessageOut)
async def delete_route(item_id: int, db: DbSession, _: AdminUser, __: SameOrigin) -> MessageOut:
    row = await db.get(Route, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    try:
        await guards.delete_route(db, row)
    except guards.DeleteBlockedError as exc:
        guards.raise_http(exc)
    return MessageOut(message="Deleted")


@router.post("/routes/reorder", response_model=MessageOut)
async def reorder_routes(
    body: ReorderRequest,
    db: DbSession,
    _: AdminUser,
    __: SameOrigin,
    province_start_id: int | None = None,
) -> MessageOut:
    # When filtered by departure province, reorder only within that scope.
    if province_start_id is not None:
        await reorder_scoped(
            db,
            Route,
            body.ids,
            scope_column="province_start_id",
            scope_value=province_start_id,
        )
    else:
        await reorder_full_table(db, Route, body.ids)
    return MessageOut(message="Reordered")


# ── Route stops ────────────────────────────────────────────────────────────
@router.get("/routes/{route_id}/stops", response_model=list[RouteStopOut])
async def list_route_stops(
    route_id: int, db: DbSession, _: AdminUser
) -> list[RouteStopOut]:
    result = await db.execute(
        select(RouteStop, Stop.name, Stop.address)
        .join(Stop, RouteStop.stop_id == Stop.id)
        .where(RouteStop.route_id == route_id)
        .order_by(RouteStop.priority.desc())
    )
    return [
        _route_stop_out(row, stop_name=name, stop_address=address)
        for row, name, address in result.all()
    ]


@router.post("/routes/{route_id}/stops", response_model=RouteStopOut, status_code=201)
async def create_route_stop(
    route_id: int, body: RouteStopWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> RouteStopOut:
    if not await db.get(Route, route_id):
        raise HTTPException(404, detail="Route not found")
    if body.stop_type not in ("pickup", "dropoff", "both"):
        raise HTTPException(422, detail="Invalid stop_type")
    stop = await db.get(Stop, body.stop_id)
    if not stop:
        raise HTTPException(404, detail="Stop not found")
    max_p = int(
        await db.scalar(
            select(func.coalesce(func.max(RouteStop.priority), 0)).where(
                RouteStop.route_id == route_id
            )
        )
        or 0
    )
    row = RouteStop(
        route_id=route_id,
        stop_id=body.stop_id,
        stop_type=body.stop_type,
        priority=body.priority if body.priority is not None else max_p + 1,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _route_stop_out(row, stop_name=stop.name, stop_address=stop.address)


@router.put("/route-stops/{item_id}", response_model=RouteStopOut)
async def update_route_stop(
    item_id: int, body: RouteStopWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> RouteStopOut:
    row = await db.get(RouteStop, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    stop = await db.get(Stop, body.stop_id)
    if not stop:
        raise HTTPException(404, detail="Stop not found")
    row.stop_id = body.stop_id
    row.stop_type = body.stop_type
    if body.priority is not None:
        row.priority = body.priority
    await db.commit()
    await db.refresh(row)
    return _route_stop_out(row, stop_name=stop.name, stop_address=stop.address)


@router.delete("/route-stops/{item_id}", response_model=MessageOut)
async def delete_route_stop(
    item_id: int, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    row = await db.get(RouteStop, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    await db.delete(row)
    await db.commit()
    return MessageOut(message="Deleted")


@router.post("/routes/{route_id}/stops/reorder", response_model=MessageOut)
async def reorder_route_stops(
    route_id: int, body: ReorderRequest, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    await reorder_scoped(
        db, RouteStop, body.ids, scope_column="route_id", scope_value=route_id
    )
    return MessageOut(message="Reordered")
