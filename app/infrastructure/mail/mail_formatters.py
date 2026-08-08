"""Display helpers for booking email templates."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin

_PAYMENT_LABELS = {
    "online_banking": "Chuyển khoản ngân hàng / Bank transfer",
    "cash_on_pickup": "Thanh toán khi lên xe / Cash on pickup",
}


def format_vnd(amount: int | float | None) -> str:
    if amount is None:
        return "0đ"
    try:
        value = int(amount)
    except (TypeError, ValueError):
        return "0đ"
    return f"{value:,}đ"


def format_booking_date(value: date | datetime | str | None) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    text = str(value).strip()
    if not text:
        return ""
    try:
        return date.fromisoformat(text[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return text


def payment_method_label(method: str | None) -> str:
    if not method:
        return ""
    return _PAYMENT_LABELS.get(method, method)


def absolute_url(url: str | None, base_url: str) -> str:
    if not url:
        return ""
    text = str(url).strip()
    if not text:
        return ""
    lower = text.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return text
    base = (base_url or "").rstrip("/") + "/"
    return urljoin(base, text.lstrip("/"))


def format_pickup_info(
    *,
    pickup_stop_id: int | None,
    pickup_name: str | None,
    pickup_address: str | None,
    hotel_address: str | None,
) -> str:
    if pickup_stop_id is None and hotel_address:
        return f"Đón tại khách sạn: {hotel_address}"
    name = (pickup_name or "").strip()
    address = (pickup_address or "").strip()
    if name and address:
        return f"{name} - {address}"
    if name:
        return name
    if address:
        return address
    if hotel_address:
        return f"Đón tại khách sạn: {hotel_address}"
    return ""


def customer_display(name: str | None, phone: str | None) -> str:
    parts = [str(p).strip() for p in (name, phone) if p and str(p).strip()]
    return " ".join(parts)


def quantity_label(quantity: Any) -> str:
    try:
        qty = int(quantity or 0)
    except (TypeError, ValueError):
        qty = 0
    return f"{qty} vé / ticket(s)"


def ticket_type(bus_model_name: str | None, bus_name: str | None) -> str:
    model = (bus_model_name or "").strip()
    if model:
        return model
    return (bus_name or "").strip()
