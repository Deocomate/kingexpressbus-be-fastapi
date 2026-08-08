"""HTTP smoke against a running uvicorn (avoids TestClient+aiomysql loop issues)."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, timedelta

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.core.security import verify_password

BASE = "http://127.0.0.1:8000"
ORIGIN = "http://localhost:3000"
ADMIN_EMAIL = "admin@kingexpressbus.com"
ADMIN_PASSWORD = "Admin@123"


def section(title: str) -> None:
    print(f"\n=== {title} ===")


async def fetch_search_pair(url: str) -> tuple[int, int]:
    eng = create_async_engine(url, pool_pre_ping=True)
    try:
        async with eng.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        select r.province_start_id, r.province_end_id
                        from trips t
                        join routes r on t.route_id = r.id
                        where t.is_active = 1
                        group by r.province_start_id, r.province_end_id
                        order by count(*) desc
                        limit 1
                        """
                    )
                )
            ).one()
            return int(row[0]), int(row[1])
    finally:
        await eng.dispose()


async def verify_admin_hash(url: str) -> bool:
    eng = create_async_engine(url, pool_pre_ping=True)
    try:
        async with eng.connect() as conn:
            row = (
                await conn.execute(
                    text("select password from users where email = :e limit 1"),
                    {"e": ADMIN_EMAIL},
                )
            ).one_or_none()
            if row is None:
                return False
            ok = verify_password(ADMIN_PASSWORD, row[0])
            print(f"bcrypt verify Admin@123: {ok} prefix={str(row[0])[:7]}")
            return ok
    finally:
        await eng.dispose()


def main() -> int:
    get_settings.cache_clear()
    settings = get_settings()
    failures = 0

    section("config")
    print(
        f"db={settings.db_username}@{settings.db_host}:{settings.db_port}/"
        f"{settings.db_database}"
    )

    section("password parity")
    if not asyncio.run(verify_admin_hash(settings.database_url)):
        print("FAIL password verify")
        return 1

    origin, dest = asyncio.run(fetch_search_pair(settings.database_url))
    travel = (date.today() + timedelta(days=7)).isoformat()
    print(f"search origin={origin} dest={dest} date={travel}")

    with httpx.Client(base_url=BASE, timeout=30.0) as client:
        section("health")
        r = client.get("/health")
        print(f"status={r.status_code} body={r.json()}")
        if r.status_code != 200:
            print("FAIL: start uvicorn first: uvicorn app.main:app --port 8000")
            return 1

        section("auth missing Origin -> 403")
        r = client.post(
            "/api/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        print(f"status={r.status_code} detail={r.json().get('detail')}")
        if r.status_code != 403:
            failures += 1

        section("auth login")
        r = client.post(
            "/api/v1/auth/login",
            headers={"Origin": ORIGIN},
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        print(f"status={r.status_code} body={r.json()}")
        cookie = r.cookies.get(settings.cookie_name)
        print(f"cookie_set={bool(cookie)}")
        if r.status_code != 200 or not cookie:
            failures += 1

        section("auth /me")
        r = client.get("/api/v1/auth/me")
        print(f"status={r.status_code} body={r.json()}")
        if r.status_code != 200:
            failures += 1

        section("admin auth login")
        r = client.post(
            "/api/v1/admin/auth/login",
            headers={"Origin": ORIGIN},
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        print(f"status={r.status_code} role={r.json().get('role')}")
        if r.status_code != 200:
            failures += 1

        section("wrong password -> 401")
        r = client.post(
            "/api/v1/auth/login",
            headers={"Origin": ORIGIN},
            json={"email": ADMIN_EMAIL, "password": "WrongPassword!"},
        )
        print(f"status={r.status_code}")
        if r.status_code != 401:
            failures += 1

        section("provinces")
        r = client.get("/api/v1/public/provinces")
        print(f"status={r.status_code} count={len(r.json()) if r.status_code==200 else 0}")
        if r.status_code != 200 or not r.json():
            failures += 1

        section("trip search")
        r = client.get(
            "/api/v1/public/trips/search",
            params={
                "origin_province_id": origin,
                "destination_province_id": dest,
                "date": travel,
            },
        )
        print(f"status={r.status_code}")
        items = r.json() if r.status_code == 200 else []
        if r.status_code != 200:
            print(r.text)
            failures += 1
        else:
            print(f"trips={len(items)}")
            if items:
                sample = {
                    k: items[0].get(k)
                    for k in (
                        "trip_id",
                        "route_slug",
                        "start_time",
                        "available_seats",
                        "effective_price",
                        "is_blocked",
                        "has_surcharge",
                        "available_hotel_pickup",
                    )
                }
                print("sample=", json.dumps(sample, ensure_ascii=True))

        section("trip detail + price")
        if items:
            trip_id = items[0]["trip_id"]
            d = client.get(f"/api/v1/public/trips/{trip_id}", params={"date": travel})
            p = client.get(
                f"/api/v1/public/trips/{trip_id}/price", params={"date": travel}
            )
            print(f"detail={d.status_code} price={p.status_code}")
            if d.status_code == 200:
                body = d.json()
                print(
                    f"stops={len(body.get('stops') or [])} "
                    f"services={body.get('bus_services')} "
                    f"effective={body.get('effective_price')}"
                )
            if p.status_code == 200:
                print("price=", json.dumps(p.json(), ensure_ascii=True))
            if d.status_code != 200 or p.status_code != 200:
                failures += 1
        else:
            print("SKIP detail (no search hits)")

        section("web-profile")
        r = client.get("/api/v1/public/web-profile")
        print(f"status={r.status_code}")
        if r.status_code == 200:
            wp = r.json()
            print(
                f"id={wp.get('id')} hotline={wp.get('hotline')} "
                f"map_len={len(wp.get('map_embedded') or '')}"
            )
        else:
            print(r.text)
            failures += 1

        section("menus")
        r = client.get("/api/v1/public/menus")
        print(f"status={r.status_code} roots={len(r.json()) if r.status_code==200 else 0}")
        if r.status_code != 200:
            failures += 1

    section("summary")
    print(f"failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
