"""Password and JWT unit tests (no DB required)."""

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_roundtrip() -> None:
    hashed = hash_password("Secret123!")
    assert hashed.startswith("$2y$")
    assert verify_password("Secret123!", hashed)
    assert not verify_password("wrong", hashed)


def test_bcrypt_2y_prefix_normalize() -> None:
    # Hash produced as $2b$, rewritten to $2y$ — verify still works
    hashed = hash_password("bcrypt-compat")
    assert hashed.startswith("$2y$")
    as_2b = "$2b$" + hashed[4:]
    assert verify_password("bcrypt-compat", as_2b)
    assert verify_password("bcrypt-compat", hashed)


def test_verify_rejects_empty() -> None:
    assert not verify_password("", "$2y$12$aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    assert not verify_password("x", None)
    assert not verify_password("x", "not-a-hash")


def test_jwt_roundtrip() -> None:
    token = create_access_token(42, "admin")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["role"] == "admin"


def test_jwt_invalid() -> None:
    assert decode_access_token("not.a.jwt") is None
