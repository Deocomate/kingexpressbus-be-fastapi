"""Trip search / details / seats — ports TripService public reads."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Booking,
    Bus,
    Province,
    Route,
    RouteStop,
    Stop,
    Trip,
    TripBlock,
    bus_bus_service,
)
from app.db.models.fleet import BusService
from app.services.pricing import calculate_breakdown
from app.services.seats import available_seats


async def _booked_map(
    db: AsyncSession, trip_ids: list[int], travel_date: date
) -> dict[int, int]:
    if not trip_ids:
        return {}
    result = await db.execute(
        select(Booking.trip_id, func.coalesce(func.sum(Booking.quantity), 0))
        .where(
            Booking.trip_id.in_(trip_ids),
            Booking.booking_date == travel_date,
            Booking.status.in_(("pending", "confirmed", "completed")),
        )
        .group_by(Booking.trip_id)
    )
    return {int(tid): int(qty) for tid, qty in result.all()}


async def _block_map(
    db: AsyncSession, trip_ids: list[int], travel_date: date
) -> dict[int, TripBlock]:
    if not trip_ids:
        return {}
    result = await db.execute(
        select(TripBlock).where(
            TripBlock.trip_id.in_(trip_ids),
            TripBlock.start_date <= travel_date,
            TripBlock.end_date >= travel_date,
        )
    )
    out: dict[int, TripBlock] = {}
    for block in result.scalars():
        # first block wins
        out.setdefault(block.trip_id, block)
    return out


async def _bus_services_map(
    db: AsyncSession, bus_ids: list[int]
) -> dict[int, list[str]]:
    if not bus_ids:
        return {}
    result = await db.execute(
        select(bus_bus_service.c.bus_id, BusService.name)
        .join(BusService, BusService.id == bus_bus_service.c.bus_service_id)
        .where(bus_bus_service.c.bus_id.in_(bus_ids))
        .order_by(BusService.priority.desc())
    )
    out: dict[int, list[str]] = {}
    for bus_id, name in result.all():
        out.setdefault(int(bus_id), []).append(name)
    return out


async def search_trips(
    db: AsyncSession,
    *,
    origin_province_id: int,
    destination_province_id: int,
    travel_date: date,
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(Trip, Route, Bus)
        .join(Route, Trip.route_id == Route.id)
        .join(Bus, Trip.bus_id == Bus.id)
        .where(
            Route.province_start_id == origin_province_id,
            Route.province_end_id == destination_province_id,
            Trip.is_active.is_(True),
        )
        .order_by(Trip.priority.desc(), Trip.start_time.asc())
    )
    rows = list(result.all())
    trip_ids = [t.id for t, _, _ in rows]
    bus_ids = [b.id for _, _, b in rows]
    booked = await _booked_map(db, trip_ids, travel_date)
    blocks = await _block_map(db, trip_ids, travel_date)
    services = await _bus_services_map(db, bus_ids)

    items: list[dict[str, Any]] = []
    for trip, route, bus in rows:
        block = blocks.get(trip.id)
        seats = available_seats(
            seat_count=bus.seat_count,
            booked_quantity=booked.get(trip.id, 0),
            block_type=block.block_type if block else None,
        )
        breakdown = await calculate_breakdown(
            db,
            route_id=route.id,
            base_unit_price=int(trip.price or 0),
            travel_date=travel_date,
        )
        items.append(
            {
                "trip_id": trip.id,
                "route_id": route.id,
                "bus_id": bus.id,
                "start_time": trip.start_time,
                "end_time": trip.end_time,
                "price": int(trip.price or 0),
                "priority": trip.priority,
                "route_name": route.name,
                "route_slug": route.slug,
                "duration": route.duration,
                "distance_km": route.distance_km,
                "available_hotel_pickup": route.available_hotel_pickup,
                "bus_name": bus.name,
                "bus_model": bus.model_name,
                "seat_count": bus.seat_count,
                "available_seats": seats,
                "is_blocked": block is not None
                and block.block_type in ("sold_out", "off_day"),
                "block_type": block.block_type if block else None,
                "bus_services": services.get(bus.id, []),
                "effective_price": breakdown["final_unit_price"],
                "has_surcharge": breakdown["has_surcharge"],
            }
        )
    return items


async def get_trip_details(
    db: AsyncSession,
    trip_id: int,
    travel_date: date,
) -> dict[str, Any] | None:
    result = await db.execute(
        select(Trip, Route, Bus)
        .join(Route, Trip.route_id == Route.id)
        .join(Bus, Trip.bus_id == Bus.id)
        .where(Trip.id == trip_id)
    )
    row = result.one_or_none()
    if row is None:
        return None
    trip, route, bus = row

    start_p = await db.get(Province, route.province_start_id)
    end_p = await db.get(Province, route.province_end_id)

    blocks = await _block_map(db, [trip.id], travel_date)
    block = blocks.get(trip.id)
    booked = await _booked_map(db, [trip.id], travel_date)
    services = await _bus_services_map(db, [bus.id])
    seats = available_seats(
        seat_count=bus.seat_count,
        booked_quantity=booked.get(trip.id, 0),
        block_type=block.block_type if block else None,
    )
    breakdown = await calculate_breakdown(
        db,
        route_id=route.id,
        base_unit_price=int(trip.price or 0),
        travel_date=travel_date,
    )

    stops_result = await db.execute(
        select(RouteStop, Stop)
        .join(Stop, RouteStop.stop_id == Stop.id)
        .where(RouteStop.route_id == route.id)
        .order_by(RouteStop.priority.desc())
    )
    stops = [
        {
            "route_stop_id": rs.id,
            "stop_id": stop.id,
            "name": stop.name,
            "address": stop.address,
            "stop_type": rs.stop_type,
            "priority": rs.priority,
        }
        for rs, stop in stops_result.all()
    ]

    return {
        "trip_id": trip.id,
        "route_id": route.id,
        "bus_id": bus.id,
        "start_time": trip.start_time,
        "end_time": trip.end_time,
        "price": int(trip.price or 0),
        "priority": trip.priority,
        "route_name": route.name,
        "route_slug": route.slug,
        "duration": route.duration,
        "distance_km": route.distance_km,
        "available_hotel_pickup": route.available_hotel_pickup,
        "bus_name": bus.name,
        "bus_model": bus.model_name,
        "seat_count": bus.seat_count,
        "available_seats": seats,
        "is_blocked": block is not None and block.block_type in ("sold_out", "off_day"),
        "block_type": block.block_type if block else None,
        "bus_services": services.get(bus.id, []),
        "effective_price": breakdown["final_unit_price"],
        "has_surcharge": breakdown["has_surcharge"],
        "start_province_name": start_p.name if start_p else None,
        "end_province_name": end_p.name if end_p else None,
        "bus_content": bus.content,
        "bus_images": bus.image_list_url,
        "is_off_day": bool(block and block.block_type == "off_day"),
        "block_note": block.note if block else None,
        "price_breakdown": breakdown,
        "stops": stops,
    }
