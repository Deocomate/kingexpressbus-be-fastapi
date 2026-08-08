"""Public read endpoints for the client portal."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.application.booking.pricing import calculate_breakdown
from app.application.catalog.trips import get_trip_details, search_trips
from app.application.website import public_content
from app.core.deps import DbSession
from app.domain.shared.errors import NotFoundError
from app.infrastructure.persistence.models import Province, Route, Trip
from app.presentation.api.v1.public_mappers import build_menu_tree, web_profile_to_out
from app.presentation.schemas.public import (
    MenuNodeOut,
    PriceBreakdownOut,
    ProvinceOut,
    RouteListOut,
    TripDetailOut,
    TripSearchItemOut,
    WebProfileOut,
)

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/web-profile", response_model=WebProfileOut)
async def get_web_profile(db: DbSession) -> WebProfileOut:
    try:
        profile = await public_content.get_default_web_profile(db)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return web_profile_to_out(profile)


@router.get("/menus", response_model=list[MenuNodeOut])
async def get_menus(db: DbSession) -> list[MenuNodeOut]:
    return build_menu_tree(await public_content.list_menus(db))


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
