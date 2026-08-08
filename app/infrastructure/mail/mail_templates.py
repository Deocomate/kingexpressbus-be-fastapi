"""Jinja2 environment and booking mail HTML rendering."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates" / "email"

_SUBJECTS = {
    "confirmation": "Tiếp nhận yêu cầu đặt vé / Booking Request Received",
    "payment_request": "Yêu cầu thanh toán / Payment Request",
    "approval": "Xác nhận đặt vé / Booking Confirmed",
    "cancellation": "Hủy đặt vé / Booking Cancelled",
}

_TEMPLATE_NAMES = {
    "confirmation": "confirmation.html",
    "payment_request": "payment_request.html",
    "approval": "approval.html",
    "cancellation": "cancellation.html",
}

_SERVICE_SUBJECTS = {
    "confirmation": {
        "hotel": "Tiếp nhận đặt phòng / Hotel Booking Received",
        "tour": "Tiếp nhận đặt tour / Tour Booking Received",
    },
    "approval": {
        "hotel": "Xác nhận đặt phòng / Hotel Booking Confirmed",
        "tour": "Xác nhận đặt tour / Tour Booking Confirmed",
    },
    "cancellation": {
        "hotel": "Hủy đặt phòng / Hotel Booking Cancelled",
        "tour": "Hủy đặt tour / Tour Booking Cancelled",
    },
}

_SERVICE_TEMPLATES = {
    "confirmation": "service_confirmation.html",
    "approval": "service_approval.html",
    "cancellation": "service_cancellation.html",
}


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_booking_mail(kind: str, details: dict[str, Any]) -> tuple[str, str]:
    if kind not in _TEMPLATE_NAMES:
        raise ValueError(f"Unknown mail kind: {kind}")
    code = details.get("booking_code") or ""
    subject_base = _SUBJECTS[kind]
    subject = f"{subject_base} #{code}" if code else subject_base
    html = _env().get_template(_TEMPLATE_NAMES[kind]).render(
        **details,
        mail_kind=kind,
        mail_title=subject_base,
    )
    return subject, html


def render_service_booking_mail(kind: str, details: dict[str, Any]) -> tuple[str, str]:
    if kind not in _SERVICE_TEMPLATES:
        raise ValueError(f"Unknown service mail kind: {kind}")
    service_kind = details.get("service_kind") or "hotel"
    subject_base = _SERVICE_SUBJECTS[kind].get(
        service_kind, _SERVICE_SUBJECTS[kind]["hotel"]
    )
    code = details.get("booking_code") or ""
    subject = f"{subject_base} #{code}" if code else subject_base
    html = _env().get_template(_SERVICE_TEMPLATES[kind]).render(
        **details,
        mail_kind=kind,
        mail_title=subject_base,
    )
    return subject, html
