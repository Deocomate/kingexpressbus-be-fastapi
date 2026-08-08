"""Admin generic-select option search (autocomplete for related-record pickers)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import or_, select

from app.core.deps import DbSession
from app.core.rate_limit import client_ip, rate_limiter
from app.infrastructure.persistence.models import (
    Bus,
    District,
    DistrictType,
    Province,
    Route,
    Stop,
    Trip,
    User,
)
from app.presentation.api.v1.admin.deps import AdminUser
from app.presentation.schemas.admin_common import OptionItem, OptionsOut

router = APIRouter(prefix="/admin", tags=["admin-meta"])


@router.get("/options/{resource}", response_model=OptionsOut)
async def options_search(
    resource: str,
    request: Request,
    db: DbSession,
    _: AdminUser,
    q: str = Query(""),
    route_id: int = 0,
) -> OptionsOut:
    rate_limiter.hit(f"admin:options:ip:{client_ip(request)}", limit=60)
    q = q.strip()
    # Route-scoped stop pickers may open with an empty query to list
    # stops in the route's start/end provinces immediately.
    allow_empty_q = resource == "stops" and bool(route_id)
    if len(q) < 2 and not allow_empty_q:
        return OptionsOut(results=[])
    like = f"%{q}%"
    results: list[OptionItem] = []

    if resource == "buses":
        rows = (
            await db.execute(select(Bus.id, Bus.name).where(Bus.name.like(like)).limit(50))
        ).all()
        results = [OptionItem(id=r[0], text=r[1]) for r in rows]
    elif resource == "routes":
        rows = (
            await db.execute(select(Route.id, Route.name).where(Route.name.like(like)).limit(50))
        ).all()
        results = [OptionItem(id=r[0], text=r[1]) for r in rows]
    elif resource == "trips":
        stmt = (
            select(Trip.id, Trip.start_time, Route.name)
            .join(Route, Trip.route_id == Route.id)
            .where(Route.name.like(like))
            .limit(50)
        )
        if route_id:
            stmt = stmt.where(Trip.route_id == route_id)
        rows = (await db.execute(stmt)).all()
        results = [
            OptionItem(id=r[0], text=f"{r[2]} @ {r[1]}") for r in rows
        ]
    elif resource == "provinces":
        rows = (
            await db.execute(
                select(Province.id, Province.name).where(Province.name.like(like)).limit(50)
            )
        ).all()
        results = [OptionItem(id=r[0], text=r[1]) for r in rows]
    elif resource == "districts":
        rows = (
            await db.execute(
                select(District.id, District.name).where(District.name.like(like)).limit(50)
            )
        ).all()
        results = [OptionItem(id=r[0], text=r[1]) for r in rows]
    elif resource == "district-types":
        rows = (
            await db.execute(
                select(DistrictType.id, DistrictType.name)
                .where(DistrictType.name.like(like))
                .limit(50)
            )
        ).all()
        results = [OptionItem(id=r[0], text=r[1]) for r in rows]
    elif resource == "stops":
        stmt = (
            select(Stop.id, Stop.name, Stop.address)
            .join(District, District.id == Stop.district_id)
            .order_by(Stop.priority.desc(), Stop.name.asc())
            .limit(100 if route_id else 50)
        )
        if route_id:
            route = await db.get(Route, route_id)
            if not route:
                return OptionsOut(results=[])
            province_ids = list(
                {route.province_start_id, route.province_end_id}
            )
            stmt = stmt.where(District.province_id.in_(province_ids))
            if len(q) >= 2:
                stmt = stmt.where(or_(Stop.name.like(like), Stop.address.like(like)))
        else:
            stmt = stmt.where(Stop.name.like(like))
        rows = (await db.execute(stmt)).all()
        results = [
            OptionItem(
                id=r[0],
                text=f"{r[1]}" + (f" — {r[2]}" if r[2] else ""),
            )
            for r in rows
        ]
    elif resource == "users":
        rows = (
            await db.execute(select(User.id, User.name).where(User.name.like(like)).limit(50))
        ).all()
        results = [OptionItem(id=r[0], text=r[1]) for r in rows]
    else:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown option source")

    return OptionsOut(results=results)
