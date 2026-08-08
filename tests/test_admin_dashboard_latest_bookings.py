"""Phase 2 dashboard parity: admin_list_bookings(upcoming=True) query shape.

Upcoming admin bookings — pending/confirmed
bookings from today onward, ordered by departure, limit 10. No live DB is
stood up here (this repo's DB-backed tests run against real MySQL via
scripts/dev/mysql_smoke_*), so the statement built by list_bookings_admin is
inspected directly via a mocked AsyncSession.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.application.booking import booking_admin_query as booking_svc
from app.main import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_upcoming_filters_to_pending_confirmed_and_orders_by_departure() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=0)
    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result
    db.execute = AsyncMock(return_value=execute_result)

    await booking_svc.list_bookings_admin(db, upcoming=True)

    count_query = str(db.scalar.call_args.args[0])
    assert "trips" in count_query  # joined for departure-time ordering
    assert "bookings.status IN" in count_query
    assert "bookings.booking_date >=" in count_query

    page_query = str(db.execute.call_args.args[0])
    assert "ORDER BY bookings.booking_date" in page_query
    assert "trips.start_time" in page_query


@pytest.mark.asyncio
async def test_non_upcoming_keeps_existing_status_and_search_filters() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=0)
    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_result
    db.execute = AsyncMock(return_value=execute_result)

    await booking_svc.list_bookings_admin(db, status_filter="confirmed", q="A01")

    compiled = str(db.scalar.call_args.args[0])
    assert "bookings.status =" in compiled
    assert "bookings.booking_code LIKE" in compiled
    assert "trips" not in compiled  # no departure join needed outside upcoming mode

    page_query = str(db.execute.call_args.args[0])
    assert "ORDER BY bookings.created_at" in page_query


def test_admin_bookings_openapi_documents_upcoming_param() -> None:
    paths = client.get("/openapi.json").json()["paths"]
    params = paths["/api/v1/admin/bookings"]["get"]["parameters"]
    names = {p["name"] for p in params}
    assert "upcoming" in names
