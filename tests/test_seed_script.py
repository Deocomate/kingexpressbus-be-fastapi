"""Unit tests for scripts/seed.py's pure-logic helpers (no DB required)."""

import json
import sys
from datetime import date, datetime, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import verify_password
from app.infrastructure.persistence.models.ops import Trip
from app.infrastructure.persistence.models.surcharge import HolidaySurcharge
from app.infrastructure.persistence.models.user import User
from scripts.seed import (
    ADMIN_PASSWORD_SENTINEL,
    coerce_row_types,
    looks_like_production,
    prepare_user_rows,
)

SEED_DATA_DIR = (
    Path(__file__).resolve().parent.parent
    / "app"
    / "infrastructure"
    / "persistence"
    / "seed_data"
)
HANOI_ORIGIN_ROUTES = {1, 65, 67, 68, 69, 70}
NOI_BAI_STOP_IDS = {24, 25}


class TestLooksLikeProduction:
    def test_flags_production_variants(self):
        assert looks_like_production("production")
        assert looks_like_production("Production")
        assert looks_like_production(" prod ")

    def test_allows_local_and_staging(self):
        assert not looks_like_production("local")
        assert not looks_like_production("staging")
        assert not looks_like_production("")


class TestPrepareUserRows:
    def test_hashes_admin_sentinel_with_verifiable_password(self):
        rows = [{"id": 1, "password": ADMIN_PASSWORD_SENTINEL, "role": "admin"}]
        prepared = prepare_user_rows(rows)
        assert prepared[0]["password"] != ADMIN_PASSWORD_SENTINEL
        assert verify_password("Admin@123", prepared[0]["password"])

    def test_leaves_non_admin_hashes_verbatim(self):
        existing_hash = "$2y$12$nJfIwnzcs4EFTRyBaC/8WONBMLaYtYm2FbJKR2rYIB7YDYocksQk2"
        rows = [{"id": 2, "password": existing_hash, "role": "customer"}]
        prepared = prepare_user_rows(rows)
        assert prepared[0]["password"] == existing_hash

    def test_does_not_mutate_input_rows(self):
        rows = [{"id": 1, "password": ADMIN_PASSWORD_SENTINEL, "role": "admin"}]
        prepare_user_rows(rows)
        assert rows[0]["password"] == ADMIN_PASSWORD_SENTINEL


class TestCoerceRowTypes:
    def test_converts_datetime_string_columns(self):
        rows = [{"id": 1, "email": None, "created_at": "2025-10-02 23:27:39"}]
        coerced = coerce_row_types(User.__table__, rows)
        # Naive by design: DB columns are naive DateTime (see app/db/base.py).
        assert coerced[0]["created_at"] == datetime(2025, 10, 2, 23, 27, 39)  # noqa: DTZ001

    def test_converts_date_columns(self):
        rows = [{"id": 1, "start_date": "2026-04-29", "end_date": "2026-05-03"}]
        coerced = coerce_row_types(HolidaySurcharge.__table__, rows)
        assert coerced[0]["start_date"] == date(2026, 4, 29)
        assert coerced[0]["end_date"] == date(2026, 5, 3)

    def test_converts_time_columns(self):
        rows = [{"id": 7, "start_time": "14:00:00", "end_time": "20:00:00"}]
        coerced = coerce_row_types(Trip.__table__, rows)
        assert coerced[0]["start_time"] == time(14, 0, 0)
        assert coerced[0]["end_time"] == time(20, 0, 0)

    def test_leaves_null_values_untouched(self):
        rows = [{"id": 1, "email": None, "created_at": None}]
        coerced = coerce_row_types(User.__table__, rows)
        assert coerced[0]["created_at"] is None


class TestNoiBaiSeedData:
    """Nội Bài stops belong to Hà Nội and only HN-origin routes as pickup."""

    def _load(self, name: str) -> list[dict]:
        return json.loads((SEED_DATA_DIR / name).read_text(encoding="utf-8"))

    def test_airport_stops_are_in_hanoi_district(self):
        stops = {row["id"]: row for row in self._load("stops.json")}
        assert 26 not in stops
        assert stops[24]["district_id"] == 1
        assert stops[25]["district_id"] == 1
        assert "Nội Bài" in stops[24]["name"]
        assert "Nội Bài" in stops[25]["name"]

    def test_noi_bai_pickup_on_hanoi_origin_routes_only(self):
        route_stops = self._load("route_stops.json")
        by_route: dict[int, set[int]] = {}
        for row in route_stops:
            if row["stop_id"] in NOI_BAI_STOP_IDS:
                assert row["stop_type"] == "pickup"
                by_route.setdefault(row["route_id"], set()).add(row["stop_id"])
        assert set(by_route) == HANOI_ORIGIN_ROUTES
        for route_id in HANOI_ORIGIN_ROUTES:
            assert by_route[route_id] == NOI_BAI_STOP_IDS

    def test_removed_from_non_hanoi_routes(self):
        route_stops = self._load("route_stops.json")
        forbidden = {
            (row["route_id"], row["stop_id"])
            for row in route_stops
            if row["route_id"] in (48, 49) and row["stop_id"] in (24, 25, 26)
        }
        assert not forbidden
        assert not any(row["stop_id"] == 26 for row in route_stops)
