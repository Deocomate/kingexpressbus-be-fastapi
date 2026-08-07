"""HMAC signed success URLs (Laravel URL::temporarySignedRoute ≈24h)."""

from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import parse_qsl, urlencode, urlparse

DEFAULT_TTL_SECONDS = 24 * 60 * 60


def sign_success_url(
    *,
    base_url: str,
    booking_id: int,
    signing_key: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: int | None = None,
) -> str:
    """Build `{base}?booking={id}&expires={ts}&signature={hmac}`."""
    ts = int(now if now is not None else time.time()) + int(ttl_seconds)
    path = base_url.split("?", 1)[0].rstrip("/")
    if "{booking}" in path:
        path = path.replace("{booking}", str(booking_id))
    query = urlencode({"expires": ts})
    to_sign = f"{path}?{query}"
    signature = hmac.new(
        signing_key.encode("utf-8"),
        to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{path}?{query}&signature={signature}"


def verify_success_url(
    *,
    url: str,
    signing_key: str,
    now: int | None = None,
) -> int | None:
    """Return booking_id if signature valid and not expired; else None."""
    parsed = urlparse(url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    signature = params.pop("signature", None)
    expires_raw = params.get("expires", "")
    try:
        expires = int(expires_raw)
    except ValueError:
        return None
    current = int(now if now is not None else time.time())
    if current > expires:
        return None

    # Rebuild the absolute URL path that was signed (scheme + netloc + path).
    path = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    query = urlencode(params)
    to_sign = f"{path}?{query}"
    expected = hmac.new(
        signing_key.encode("utf-8"),
        to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not signature or not hmac.compare_digest(expected, signature):
        return None

    booking_part = path.rsplit("/", 1)[-1]
    try:
        return int(booking_part)
    except ValueError:
        return None


def verify_success_token(
    *,
    booking_id: int,
    expires: int,
    signature: str,
    path_template: str,
    signing_key: str,
    now: int | None = None,
) -> bool:
    """Verify discrete query params against a path template containing {booking}."""
    path = path_template.replace("{booking}", str(booking_id)).rstrip("/")
    current = int(now if now is not None else time.time())
    if current > int(expires):
        return False
    query = urlencode({"expires": int(expires)})
    to_sign = f"{path}?{query}"
    expected = hmac.new(
        signing_key.encode("utf-8"),
        to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
