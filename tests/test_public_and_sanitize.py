"""Unit tests for seat math and HTML sanitizer (no DB)."""

from app.application.booking.seats import available_seats
from app.application.catalog.html_sanitize import sanitize, sanitize_map


def test_available_seats_normal() -> None:
    assert available_seats(seat_count=40, booked_quantity=5, block_type=None) == 35


def test_available_seats_floor_at_zero() -> None:
    assert available_seats(seat_count=10, booked_quantity=15, block_type=None) == 0


def test_available_seats_sold_out_block() -> None:
    assert available_seats(seat_count=40, booked_quantity=0, block_type="sold_out") == 0


def test_available_seats_off_day_block() -> None:
    assert available_seats(seat_count=40, booked_quantity=0, block_type="off_day") == 0


def test_sanitize_strips_script() -> None:
    html = '<p>Hi</p><script>alert(1)</script>'
    out = sanitize(html)
    assert "<script>" not in out
    assert "Hi" in out


def test_sanitize_map_keeps_iframe() -> None:
    html = (
        '<iframe src="https://maps.google.com/maps?q=hanoi" width="600" '
        'height="400"></iframe><script>x</script>'
    )
    out = sanitize_map(html)
    assert "<iframe" in out
    assert "maps.google.com" in out
    assert "<script>" not in out


def test_public_openapi_paths() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/public/web-profile" in paths
    assert "/api/v1/public/menus" in paths
    assert "/api/v1/public/provinces" in paths
    assert "/api/v1/public/routes" in paths
    assert "/api/v1/public/trips/search" in paths
    assert "/api/v1/public/trips/{trip_id}" in paths
    assert "/api/v1/public/trips/{trip_id}/price" in paths
