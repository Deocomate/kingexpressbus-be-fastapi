"""Admin dashboard aggregate stats (today/total revenue, status counts, 12-month trend)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, select, text

from app.core.deps import DbSession
from app.infrastructure.persistence.models import Booking
from app.presentation.api.v1.admin.deps import AdminUser
from app.presentation.schemas.admin_meta import DashboardStatsOut

router = APIRouter(prefix="/admin", tags=["admin-meta"])


@router.get("/dashboard/stats", response_model=DashboardStatsOut)
async def dashboard_stats(db: DbSession, _: AdminUser) -> DashboardStatsOut:
    today = date.today()
    total_today = int(
        await db.scalar(
            select(func.count()).select_from(Booking).where(Booking.booking_date == today)
        )
        or 0
    )
    pending_total = int(
        await db.scalar(
            select(func.count()).select_from(Booking).where(Booking.status == "pending")
        )
        or 0
    )
    revenue_today = int(
        await db.scalar(
            select(func.coalesce(func.sum(Booking.total_price), 0)).where(
                Booking.booking_date == today,
                Booking.status.in_(("confirmed", "completed")),
            )
        )
        or 0
    )
    total_revenue = int(
        await db.scalar(
            select(func.coalesce(func.sum(Booking.total_price), 0)).where(
                Booking.status.in_(("confirmed", "completed"))
            )
        )
        or 0
    )
    status_rows = (
        await db.execute(
            select(Booking.status, func.count()).group_by(Booking.status)
        )
    ).all()
    status_counts = {str(s): int(c) for s, c in status_rows}

    monthly: list[dict[str, Any]] = []
    start = (today.replace(day=1) - timedelta(days=330)).replace(day=1)
    rows = (
        await db.execute(
            text(
                """
                SELECT YEAR(booking_date) AS y, MONTH(booking_date) AS m,
                       COALESCE(SUM(total_price), 0) AS total
                FROM bookings
                WHERE status IN ('confirmed', 'completed')
                  AND booking_date >= :start
                GROUP BY YEAR(booking_date), MONTH(booking_date)
                ORDER BY y, m
                """
            ),
            {"start": start.isoformat()},
        )
    ).all()
    keyed = {f"{int(r.m):02d}/{int(r.y)}": int(r.total) for r in rows}
    cursor = today.replace(day=1)
    for _ in range(12):
        key = f"{cursor.month:02d}/{cursor.year}"
        monthly.append({"month": key, "total": keyed.get(key, 0)})
        # step back one month
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    monthly.reverse()

    return DashboardStatsOut(
        total_today=total_today,
        pending_total=pending_total,
        revenue_today=revenue_today,
        total_revenue=total_revenue,
        status_counts=status_counts,
        monthly_revenue=monthly,
    )
