"""Signed success URL helpers for hotel/tour (mirrors bus booking contract)."""

from __future__ import annotations

from app.core.config import Settings
from app.infrastructure.storage import signed_urls


def issue_signed_success_url(
    settings: Settings, *, booking_id: int, path_template: str
) -> str:
    base = settings.frontend_base_url.rstrip("/") + path_template
    return signed_urls.sign_success_url(
        base_url=base,
        booking_id=booking_id,
        signing_key=settings.success_url_signing_key,
    )


def absolute_path_template(settings: Settings, path_template: str) -> str:
    return settings.frontend_base_url.rstrip("/") + path_template


def verify_signed_booking_access(
    *,
    settings: Settings,
    booking_id: int,
    expires: int,
    signature: str,
    path_template: str,
) -> bool:
    return signed_urls.verify_success_token(
        booking_id=booking_id,
        expires=expires,
        signature=signature,
        path_template=absolute_path_template(settings, path_template),
        signing_key=settings.success_url_signing_key,
    )
