"""Additive holiday surcharge pricing (ports HolidaySurchargeService)."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models import (
    HolidaySurcharge,
    HolidaySurchargeRoute,
    Trip,
)


def _format_vnd(amount: int) -> str:
    """Format thousands like '1,000' → '1,000'."""
    return f"{amount:,}"


def _reason_label(name: str | None, global_amount: int, route_amount: int) -> str | None:
    if (global_amount + route_amount) <= 0:
        return None
    segments: list[str] = []
    if global_amount > 0:
        segments.append(f"global +{_format_vnd(global_amount)}đ")
    if route_amount > 0:
        segments.append(f"route +{_format_vnd(route_amount)}đ")
    label = (name or "Holiday surcharge").strip()
    return f"{label} ({', '.join(segments)})"


async def calculate_breakdown(
    db: AsyncSession,
    *,
    route_id: int,
    base_unit_price: int,
    travel_date: date,
) -> dict[str, Any]:
    """Every active overlapping rule contributes; route amounts stack on global."""
    base = max(0, int(base_unit_price))
    result = await db.execute(
        select(HolidaySurcharge)
        .where(
            HolidaySurcharge.is_active.is_(True),
            HolidaySurcharge.start_date <= travel_date,
            HolidaySurcharge.end_date >= travel_date,
        )
        .order_by(HolidaySurcharge.priority.desc(), HolidaySurcharge.start_date.asc())
    )
    rules = list(result.scalars().all())
    if not rules:
        return {
            "travel_date": travel_date.isoformat(),
            "base_unit_price": base,
            "global_surcharge_unit": 0,
            "route_surcharge_unit": 0,
            "total_surcharge_unit": 0,
            "final_unit_price": base,
            "has_surcharge": False,
            "surcharge_reasons": [],
            "surcharge_reason_snapshot": None,
        }

    rule_ids = [r.id for r in rules]
    pivot_result = await db.execute(
        select(HolidaySurchargeRoute).where(
            HolidaySurchargeRoute.route_id == route_id,
            HolidaySurchargeRoute.holiday_surcharge_id.in_(rule_ids),
        )
    )
    pivots = {p.holiday_surcharge_id: p.route_surcharge_amount for p in pivot_result.scalars()}

    global_unit = 0
    route_unit = 0
    reasons: list[str] = []
    for rule in rules:
        g = int(rule.global_surcharge_amount or 0)
        r = int(pivots.get(rule.id, 0) or 0)
        global_unit += g
        route_unit += r
        label = _reason_label(rule.name, g, r)
        if label:
            reasons.append(label)

    total = global_unit + route_unit
    snapshot = "; ".join(reasons) if reasons else None
    return {
        "travel_date": travel_date.isoformat(),
        "base_unit_price": base,
        "global_surcharge_unit": global_unit,
        "route_surcharge_unit": route_unit,
        "total_surcharge_unit": total,
        "final_unit_price": max(0, base + total),
        "has_surcharge": total > 0,
        "surcharge_reasons": reasons,
        "surcharge_reason_snapshot": snapshot,
    }


async def resolve_effective_price(
    db: AsyncSession,
    *,
    trip_id: int,
    booking_date: date,
) -> dict[str, Any]:
    """Ports HolidaySurchargeService::calculateBreakdownByTripId."""
    trip = await db.get(Trip, trip_id)
    if trip is None:
        return {
            "travel_date": booking_date.isoformat(),
            "base_unit_price": 0,
            "global_surcharge_unit": 0,
            "route_surcharge_unit": 0,
            "total_surcharge_unit": 0,
            "final_unit_price": 0,
            "has_surcharge": False,
            "surcharge_reasons": [],
            "surcharge_reason_snapshot": None,
        }
    return await calculate_breakdown(
        db,
        route_id=trip.route_id,
        base_unit_price=int(trip.price or 0),
        travel_date=booking_date,
    )
