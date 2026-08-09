"""Unit tests for trip search/detail public schemas (no DB)."""

from datetime import time

from app.presentation.schemas.public import TripDetailOut, TripSearchItemOut


class TestTripSearchItemImages:
    def test_search_item_accepts_bus_images_and_thumbnail(self):
        item = TripSearchItemOut(
            trip_id=1,
            route_id=1,
            bus_id=7,
            start_time=time(7, 0),
            end_time=time(13, 15),
            price=380000,
            priority=1,
            route_name="Hà Nội - Sapa",
            route_slug="ha-noi-sapa",
            available_hotel_pickup=True,
            bus_name="VIP 22 cabin single",
            seat_count=20,
            available_seats=10,
            bus_images=["/assets/client/images/kingexpressbus/cabin/1.jpg"],
            thumbnail_url="/assets/client/images/kingexpressbus/cabin/1.jpg",
        )
        assert item.bus_images[0].endswith("cabin/1.jpg")
        assert item.thumbnail_url.endswith("cabin/1.jpg")

    def test_detail_inherits_bus_images_from_search_item(self):
        detail = TripDetailOut(
            trip_id=1,
            route_id=1,
            bus_id=1,
            start_time=time(22, 0),
            end_time=time(5, 30),
            price=250000,
            priority=1,
            route_name="Hà Nội - Sapa",
            route_slug="ha-noi-sapa",
            available_hotel_pickup=True,
            bus_name="Sleeper",
            seat_count=48,
            available_seats=40,
            bus_images=["/assets/client/images/kingexpressbus/sleeper/1.jpg"],
            thumbnail_url="/assets/client/images/kingexpressbus/sleeper/1.jpg",
        )
        assert detail.bus_images[0].endswith("sleeper/1.jpg")
