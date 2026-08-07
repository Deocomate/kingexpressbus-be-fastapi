"""Shared fixtures for admin-CRUD tests that need a real (scratch) MySQL DB.

Every other test file in this repo either mocks the DB session or avoids the
DB entirely (see test_admin_dashboard_latest_bookings.py docstring). Admin
CRUD coverage genuinely needs round-trips through SQLAlchemy + MySQL (unique
constraints, FK guards, pivot tables), so this fixture set stands up a
disposable `kingexpressbus_test` schema on the same MySQL server the app
already talks to (see `.env` DB_HOST/DB_PORT), runs the real Alembic
migration against it, and tears it down after the session.

DB_* must be overridden via environment variables *before* any `app.*`
module is imported — `app/db/session.py` builds its engine from
`get_settings()` at import time, and `alembic/env.py` does the same in its
own subprocess. This is why the override happens at module import time here,
before pytest collects any other test module that imports `app.main`.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

REPO_ROOT = Path(__file__).resolve().parent.parent

TEST_DB_HOST = os.environ.get("TEST_DB_HOST", "127.0.0.1")
TEST_DB_PORT = int(os.environ.get("TEST_DB_PORT", "3307"))
TEST_DB_USERNAME = os.environ.get("TEST_DB_USERNAME", "root")
TEST_DB_PASSWORD = os.environ.get("TEST_DB_PASSWORD", "admin")
TEST_DB_NAME = os.environ.get("TEST_DATABASE_NAME", "kingexpressbus_test")

# Must happen before any `app.*` import anywhere in the test session.
os.environ["DB_HOST"] = TEST_DB_HOST
os.environ["DB_PORT"] = str(TEST_DB_PORT)
os.environ["DB_DATABASE"] = TEST_DB_NAME
os.environ["DB_USERNAME"] = TEST_DB_USERNAME
os.environ["DB_PASSWORD"] = TEST_DB_PASSWORD

ADMIN_EMAIL = "admin@kingexpressbus.com"
ADMIN_PASSWORD = "Admin@123"
ORIGIN = "http://localhost:3000"


async def _create_schema() -> None:
    import aiomysql

    conn = await aiomysql.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USERNAME,
        password=TEST_DB_PASSWORD,
        db="mysql",
    )
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{TEST_DB_NAME}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        await conn.commit()
    finally:
        conn.close()


async def _drop_schema() -> None:
    import aiomysql

    conn = await aiomysql.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USERNAME,
        password=TEST_DB_PASSWORD,
        db="mysql",
    )
    try:
        async with conn.cursor() as cur:
            await cur.execute(f"DROP DATABASE IF EXISTS `{TEST_DB_NAME}`")
        await conn.commit()
    finally:
        conn.close()


def _run_alembic_upgrade() -> None:
    env = dict(os.environ)
    env["DB_HOST"] = TEST_DB_HOST
    env["DB_PORT"] = str(TEST_DB_PORT)
    env["DB_DATABASE"] = TEST_DB_NAME
    env["DB_USERNAME"] = TEST_DB_USERNAME
    env["DB_PASSWORD"] = TEST_DB_PASSWORD
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "alembic upgrade head failed for test DB:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


async def _seed_admin_user() -> None:
    """Insert the admin user via a throwaway connection (own event loop).

    Deliberately avoids `app.db.session.AsyncSessionLocal` — that engine's
    connection pool gets bound to whichever event loop first uses it, and
    this fixture runs inside a short-lived `asyncio.run()` loop that closes
    immediately after. Reusing the pooled connection from a later, different
    loop (e.g. the TestClient's ASGI portal thread) raises
    `RuntimeError: Event loop is closed` on hand-back to the pool.
    """
    import aiomysql

    from app.core.security import hash_password

    conn = await aiomysql.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USERNAME,
        password=TEST_DB_PASSWORD,
        db=TEST_DB_NAME,
    )
    try:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM users WHERE id = 1")
            if await cur.fetchone():
                return
            await cur.execute(
                "INSERT INTO users (name, email, phone, password, role) "
                "VALUES (%s, %s, %s, %s, %s)",
                ("Admin", ADMIN_EMAIL, "0900000000", hash_password(ADMIN_PASSWORD), "admin"),
            )
        await conn.commit()
    finally:
        conn.close()


async def _seed_default_web_profile() -> None:
    """Insert the single default web profile row (real Laravel data always
    has exactly one). Website admin tests only cover get/update — there is
    no create endpoint — so a row must exist up front.
    """
    import aiomysql

    conn = await aiomysql.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USERNAME,
        password=TEST_DB_PASSWORD,
        db=TEST_DB_NAME,
    )
    try:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM web_profiles WHERE id = 1")
            if await cur.fetchone():
                return
            await cur.execute(
                "INSERT INTO web_profiles (profile_name, is_default) VALUES (%s, %s)",
                ("King Express Bus", True),
            )
        await conn.commit()
    finally:
        conn.close()


@pytest.fixture(scope="session", autouse=True)
def _test_database() -> None:
    """Create a scratch MySQL schema, run migrations, seed baseline rows."""
    asyncio.run(_create_schema())
    _run_alembic_upgrade()
    asyncio.run(_seed_admin_user())
    asyncio.run(_seed_default_web_profile())
    yield

    async def _teardown() -> None:
        from app.db.session import engine

        await engine.dispose()
        await _drop_schema()

    asyncio.run(_teardown())


@pytest_asyncio.fixture
async def admin_client() -> AsyncIterator[httpx.AsyncClient]:
    """Async client logged in as the seeded admin (session cookie retained).

    Uses `httpx.AsyncClient` + `ASGITransport` (in-process, same event loop)
    rather than `starlette.testclient.TestClient` — the sync `TestClient`
    drives the ASGI app from a background thread with its own event loop,
    which on Windows breaks aiomysql's connection pool (opened in one loop,
    torn down from another). Running in-process on the session-scoped loop
    (see pytest.ini `asyncio_default_fixture_loop_scope`) keeps every DB
    connection on one loop for the whole test session.
    """
    from app.core.rate_limit import rate_limiter
    from app.main import app

    # Every test in this module logs in fresh, which would otherwise trip
    # the admin-login rate limiter (5/60s combo, 20/60s per-IP) after a
    # handful of test functions. The limiter is a real anti-brute-force
    # control, not something to weaken in app code for tests — clear its
    # in-memory buckets instead, scoped to this fixture only.
    rate_limiter._hits.clear()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver", headers={"Origin": ORIGIN}
    ) as client:
        r = await client.post(
            "/api/v1/admin/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert r.status_code == 200, r.text
        yield client
