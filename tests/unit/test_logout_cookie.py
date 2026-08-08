"""Logout must clear the session cookie with matching Set-Cookie attributes."""

from __future__ import annotations

from unittest.mock import MagicMock

from starlette.responses import Response

from app.api.v1.auth.session import _clear_session_cookie, _set_session_cookie


def test_clear_session_cookie_matches_set_attrs() -> None:
    settings = MagicMock()
    settings.cookie_name = "keb_session"
    settings.cookie_secure = True
    settings.cookie_samesite = "none"
    settings.jwt_expire_minutes = 60

    set_response = Response()
    _set_session_cookie(set_response, "token-value", settings)
    set_header = set_response.headers.get("set-cookie", "")
    assert "keb_session=" in set_header
    assert "Secure" in set_header
    assert "SameSite=none" in set_header or "SameSite=None" in set_header

    clear_response = Response()
    _clear_session_cookie(clear_response, settings)
    clear_header = clear_response.headers.get("set-cookie", "")
    assert "keb_session=" in clear_header
    assert "Max-Age=0" in clear_header or "max-age=0" in clear_header.lower()
    assert "Secure" in clear_header
    assert "SameSite=none" in clear_header or "SameSite=None" in clear_header
