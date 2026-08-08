"""Delete guards — block when bookings still reference the entity."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models import (
    Booking,
    Bus,
    District,
    Province,
    Route,
    Stop,
    Trip,
)


class DeleteBlockedError(Exception):
    def __init__(self, message: str, booking_count: int = 0) -> None:
        super().__init__(message)
        self.booking_count = booking_count
        self.message = message


def raise_http(exc: DeleteBlockedError) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"message": exc.message, "booking_count": exc.booking_count},
    )


def assert_none(count: int, label: str = "") -> None:
    if count <= 0:
        return
    message = (
        f"Không thể xóa {label}: còn {count} đơn đặt vé liên quan."
        if label
        else f"Không thể xóa: còn {count} đơn đặt vé liên quan."
    )
    raise DeleteBlockedError(message, count)


async def bus_booking_count(db: AsyncSession, bus_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(Booking)
            .join(Trip, Booking.trip_id == Trip.id)
            .where(Trip.bus_id == bus_id)
        )
        or 0
    )


async def route_booking_count(db: AsyncSession, route_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(Booking)
            .join(Trip, Booking.trip_id == Trip.id)
            .where(Trip.route_id == route_id)
        )
        or 0
    )


async def trip_booking_count(db: AsyncSession, trip_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count()).select_from(Booking).where(Booking.trip_id == trip_id)
        )
        or 0
    )


async def stop_booking_count(db: AsyncSession, stop_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(Booking)
            .where(
                or_(
                    Booking.pickup_stop_id == stop_id,
                    Booking.dropoff_stop_id == stop_id,
                )
            )
        )
        or 0
    )


async def district_booking_count(db: AsyncSession, district_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count(distinct(Booking.id)))
            .select_from(Booking)
            .join(
                Stop,
                or_(
                    Booking.pickup_stop_id == Stop.id,
                    Booking.dropoff_stop_id == Stop.id,
                ),
            )
            .where(Stop.district_id == district_id)
        )
        or 0
    )


async def province_booking_count(db: AsyncSession, province_id: int) -> int:
    """Bookings linked via stops in the province OR via routes start/end here."""
    via_stops = (
        select(Booking.id)
        .join(
            Stop,
            or_(
                Booking.pickup_stop_id == Stop.id,
                Booking.dropoff_stop_id == Stop.id,
            ),
        )
        .join(District, Stop.district_id == District.id)
        .where(District.province_id == province_id)
    )
    via_routes = (
        select(Booking.id)
        .join(Trip, Booking.trip_id == Trip.id)
        .join(Route, Trip.route_id == Route.id)
        .where(
            or_(
                Route.province_start_id == province_id,
                Route.province_end_id == province_id,
            )
        )
    )
    unioned = via_stops.union(via_routes).subquery()
    return int(
        await db.scalar(select(func.count()).select_from(unioned)) or 0
    )


async def delete_bus(db: AsyncSession, bus: Bus) -> None:
    assert_none(await bus_booking_count(db, bus.id), f'xe "{bus.name}"')
    await db.delete(bus)
    await db.commit()


async def delete_route(db: AsyncSession, route: Route) -> None:
    assert_none(await route_booking_count(db, route.id), f'tuyến "{route.name}"')
    await db.delete(route)
    await db.commit()


async def delete_trip(db: AsyncSession, trip: Trip) -> None:
    assert_none(await trip_booking_count(db, trip.id), f"chuyến {trip.id}")
    await db.delete(trip)
    await db.commit()


async def delete_stop(db: AsyncSession, stop: Stop) -> None:
    assert_none(await stop_booking_count(db, stop.id), "điểm dừng")
    await db.delete(stop)
    await db.commit()


async def delete_district(db: AsyncSession, district: District) -> None:
    assert_none(await district_booking_count(db, district.id), "địa điểm")
    await db.delete(district)
    await db.commit()


async def delete_province(db: AsyncSession, province: Province) -> None:
    assert_none(await province_booking_count(db, province.id), "tỉnh/thành")
    await db.delete(province)
    await db.commit()
