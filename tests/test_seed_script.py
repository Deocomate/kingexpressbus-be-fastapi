"""Unit tests for scripts/seed.py's pure-logic helpers (no DB required)."""

import sys
from datetime import date, datetime, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import verify_password
from app.db.models.ops import Trip
from app.db.models.surcharge import HolidaySurcharge
from app.db.models.user import User
from scripts.seed import (
    ADMIN_PASSWORD_SENTINEL,
    coerce_row_types,
    looks_like_production,
    prepare_user_rows,
)


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
