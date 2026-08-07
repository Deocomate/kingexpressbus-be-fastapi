"""Jinja2 environment and booking mail HTML rendering."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"

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
