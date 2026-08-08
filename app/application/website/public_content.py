"""Website / public CMS use cases (return ORM / plain data — map in presentation)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.shared.errors import NotFoundError
from app.infrastructure.persistence.models import (
    District,
    Menu,
    Province,
    RouteStop,
    Stop,
    WebProfile,
)


@dataclass(frozen=True, slots=True)
class OfficeRow:
    id: int
    name: str
    address: str | None
    district_name: str
    province_id: int
    province_name: str
    province_priority: int
    stop_priority: int


async def get_default_web_profile(db: AsyncSession) -> WebProfile:
    result = await db.execute(
        select(WebProfile).where(WebProfile.is_default.is_(True)).limit(1)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        result = await db.execute(select(WebProfile).limit(1))
        profile = result.scalar_one_or_none()
    if profile is None:
        raise NotFoundError("Web profile not found")
    return profile


async def list_menus(db: AsyncSession) -> list[Menu]:
    result = await db.execute(select(Menu))
    return list(result.scalars().all())


async def list_route_offices(db: AsyncSession) -> list[OfficeRow]:
    """Stops used as route pickup/dropoff — default public office directory."""
    route_stop_ids = select(RouteStop.stop_id).distinct()
    result = await db.execute(
        select(Stop, District, Province)
        .join(District, Stop.district_id == District.id)
        .join(Province, District.province_id == Province.id)
        .where(Stop.id.in_(route_stop_ids))
        .order_by(
            Province.priority.desc(),
            Province.name.asc(),
            Stop.priority.desc(),
            Stop.name.asc(),
        )
    )
    rows: list[OfficeRow] = []
    for stop, district, province in result.all():
        rows.append(
            OfficeRow(
                id=int(stop.id),
                name=stop.name,
                address=stop.address,
                district_name=district.name,
                province_id=int(province.id),
                province_name=province.name,
                province_priority=int(province.priority or 0),
                stop_priority=int(stop.priority or 0),
            )
        )
    return rows
