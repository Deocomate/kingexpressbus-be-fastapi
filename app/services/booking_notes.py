"""Booking notes prefixes — ports BookingService note conventions."""

from __future__ import annotations

NOTE_HOTEL_PICKUP_PREFIX = "[HOTEL_PICKUP]: "
LEGACY_NOTE_HOTEL_PICKUP_PREFIX = "[Đón tại khách sạn]: "
NOTE_CUSTOMER_PREFIX = "[CUSTOMER_NOTE]: "
NOTE_CANCEL_PREFIX = "[CANCEL_REASON]: "
NOTE_ADMIN_CANCEL_PREFIX = "[ADMIN_CANCEL_REASON]: "
LEGACY_NOTE_ADMIN_CANCEL_PREFIX = "[Lý do hủy Admin]: "
NOTE_SEPAY_REFUND_PREFIX = "[SEPAY_REFUND_REQUIRED]: "


def strip_user_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.replace("<", "").replace(">", "").strip()


def extract_hotel_pickup_address(notes: str | None) -> str | None:
    if not isinstance(notes, str) or not notes.strip():
        return None
    for prefix in (NOTE_HOTEL_PICKUP_PREFIX, LEGACY_NOTE_HOTEL_PICKUP_PREFIX):
        if prefix in notes:
            rest = notes.split(prefix, 1)[1]
            return rest.split("\n", 1)[0].strip() or None
    return None


def build_hotel_pickup_notes(
    *,
    hotel_address: str,
    customer_notes: str | None = None,
) -> str:
    parts = [f"{NOTE_HOTEL_PICKUP_PREFIX}{hotel_address.strip()}"]
    if customer_notes and customer_notes.strip():
        parts.append(f"{NOTE_CUSTOMER_PREFIX}{customer_notes.strip()}")
    return "\n".join(parts)


def notes_contain(notes: str | None, *needles: str) -> bool:
    if not notes:
        return False
    return any(n in notes for n in needles)


def append_note(existing: str | None, line: str) -> str:
    base = (existing or "").rstrip()
    if not base:
        return line
    return f"{base}\n{line}"


def sepay_refund_note(transaction_id: str) -> str:
    return (
        f"{NOTE_SEPAY_REFUND_PREFIX}"
        f"Manual refund/reconciliation required for SePay transaction "
        f"{transaction_id}."
    )
