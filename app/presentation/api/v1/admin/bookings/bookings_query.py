"""Admin booking list/counts/detail (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.application.booking import booking_admin_query as booking_query
from app.core.deps import DbSession
from app.presentation.api.v1.admin.bookings._shared import booking_out
from app.presentation.api.v1.admin.deps import AdminUser
from app.presentation.schemas.admin_common import Paginated
from app.presentation.schemas.booking import BookingOut

router = APIRouter(prefix="/admin/bookings", tags=["admin-bookings"])


@router.get("", response_model=Paginated[BookingOut])
async def admin_list_bookings(
    db: DbSession,
    _admin: AdminUser,
    page: int = 1,
    page_size: int = 25,
    status: str | None = None,
    q: str | None = None,
    upcoming: bool = False,
) -> Paginated[BookingOut]:
    """`upcoming=true` filters to
    next 10 pending/confirmed bookings ordered by departure (status/q/page ignored).
    """
    if upcoming:
        page, page_size = 1, 10
    items, total = await booking_query.list_bookings_admin(
        db, page=page, page_size=page_size, status_filter=status, q=q, upcoming=upcoming
    )
    return Paginated(
        items=[booking_out(b) for b in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/counts", response_model=dict[str, int])
async def admin_booking_counts(db: DbSession, _admin: AdminUser) -> dict[str, int]:
    return await booking_query.count_bookings_by_status(db)


@router.get("/{booking_id}", response_model=BookingOut)
async def admin_get_booking(
    booking_id: int,
    db: DbSession,
    _admin: AdminUser,
) -> BookingOut:
    booking = await booking_query.get_booking_by_id(db, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking_out(booking)
