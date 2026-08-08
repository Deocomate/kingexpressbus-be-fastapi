"""Public read endpoints for the client portal."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.db.models import Menu, Province, Route, Trip, WebProfile
from app.schemas.public import (
    MenuNodeOut,
    PriceBreakdownOut,
    ProvinceOut,
    RouteListOut,
    TripDetailOut,
    TripSearchItemOut,
    WebProfileOut,
)
from app.services import html_sanitize
from app.services.pricing import calculate_breakdown
from app.services.trips import get_trip_details, search_trips

router = APIRouter(prefix="/public", tags=["public"])


def _build_menu_tree(menus: list[Menu]) -> list[MenuNodeOut]:
    by_parent: dict[int, list[Menu]] = {}
    for m in menus:
        pid = m.parent_id if m.parent_id is not None else -1
        by_parent.setdefault(pid, []).append(m)

    def children_of(parent_id: int, depth: int = 0) -> list[MenuNodeOut]:
        if depth > 4:
            return []
        nodes = sorted(by_parent.get(parent_id, []), key=lambda x: (-x.priority, x.id))
        return [
            MenuNodeOut(
                id=m.id,
                name=m.name,
                url=m.url,
                parent_id=m.parent_id,
                priority=m.priority,
                type=m.type,
                related_id=m.related_id,
                children=children_of(m.id, depth + 1),
            )
            for m in nodes
        ]

    # Roots are parent_id == -1
    return children_of(-1)


@router.get("/web-profile", response_model=WebProfileOut)
async def get_web_profile(db: DbSession) -> WebProfileOut:
    result = await db.execute(
        select(WebProfile).where(WebProfile.is_default.is_(True)).limit(1)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        result = await db.execute(select(WebProfile).limit(1))
        profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Web profile not found")

    return WebProfileOut(
        id=profile.id,
        profile_name=profile.profile_name,
        online_payment_enabled=bool(profile.online_payment_enabled),
        title=profile.title,
        description=profile.description,
        logo_url=profile.logo_url,
        favicon_url=profile.favicon_url,
        email=profile.email,
        phone=profile.phone,
        hotline=profile.hotline,
        whatsapp=profile.whatsapp,
        address=profile.address,
        facebook_url=profile.facebook_url,
        zalo_url=profile.zalo_url,
        map_embedded=html_sanitize.sanitize_map(profile.map_embedded),
        policy_content=html_sanitize.sanitize(profile.policy_content),
        introduction_content=html_sanitize.sanitize(profile.introduction_content),
    )


@router.get("/menus", response_model=list[MenuNodeOut])
async def get_menus(db: DbSession) -> list[MenuNodeOut]:
    result = await db.execute(select(Menu))
    return _build_menu_tree(list(result.scalars().all()))


@router.get("/provinces", response_model=list[ProvinceOut])
async def list_provinces(db: DbSession) -> list[Province]:
    result = await db.execute(
        select(Province).order_by(Province.priority.desc(), Province.name.asc())
    )
    return list(result.scalars().all())


@router.get("/routes", response_model=list[RouteListOut])
async def list_routes(
    db: DbSession,
    origin_province_id: int | None = None,
    destination_province_id: int | None = None,
) -> list[Route]:
    stmt = select(Route).order_by(Route.priority.desc(), Route.name.asc())
    if origin_province_id is not None:
        stmt = stmt.where(Route.province_start_id == origin_province_id)
    if destination_province_id is not None:
        stmt = stmt.where(Route.province_end_id == destination_province_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/routes/{slug}", response_model=RouteListOut)
async def get_route_by_slug(slug: str, db: DbSession) -> Route:
    result = await db.execute(select(Route).where(Route.slug == slug))
    route = result.scalar_one_or_none()
    if route is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Route not found")
    return route


@router.get("/trips/search", response_model=list[TripSearchItemOut])
async def trips_search(
    db: DbSession,
    origin_province_id: int = Query(...),
    destination_province_id: int = Query(...),
    date: date = Query(..., description="ISO YYYY-MM-DD"),
) -> list[TripSearchItemOut]:
    items = await search_trips(
        db,
        origin_province_id=origin_province_id,
        destination_province_id=destination_province_id,
        travel_date=date,
    )
    return [TripSearchItemOut.model_validate(i) for i in items]


@router.get("/trips/{trip_id}", response_model=TripDetailOut)
async def trip_detail(
    trip_id: int,
    db: DbSession,
    date: date = Query(..., description="ISO YYYY-MM-DD"),
) -> TripDetailOut:
    detail = await get_trip_details(db, trip_id, date)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Trip not found")
    return TripDetailOut.model_validate(detail)


@router.get("/trips/{trip_id}/price", response_model=PriceBreakdownOut)
async def trip_price(
    trip_id: int,
    db: DbSession,
    date: date = Query(..., description="ISO YYYY-MM-DD"),
) -> PriceBreakdownOut:
    trip = await db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Trip not found")
    breakdown = await calculate_breakdown(
        db,
        route_id=trip.route_id,
        base_unit_price=int(trip.price or 0),
        travel_date=date,
    )
    return PriceBreakdownOut.model_validate(breakdown)
