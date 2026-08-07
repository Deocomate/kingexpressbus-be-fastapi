"""Shared seat-availability math (TripService::calculateAvailableSeats)."""


def available_seats(
    *,
    seat_count: int,
    booked_quantity: int,
    block_type: str | None,
) -> int:
    """Return available seats for a trip on a date.

    sold_out / off_day blocks → 0.
    Otherwise max(0, seat_count − booked where status in pending|confirmed|completed).
    """
    if block_type in ("sold_out", "off_day"):
        return 0
    return max(0, int(seat_count) - int(booked_quantity))
