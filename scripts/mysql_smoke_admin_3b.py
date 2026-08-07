"""Quick MySQL smoke for admin 3B list/options/dashboard (read-only)."""

from __future__ import annotations

import sys

import httpx

from app.core.config import get_settings

BASE = "http://127.0.0.1:8000"
ORIGIN = "http://localhost:3000"
ADMIN_EMAIL = "admin@kingexpressbus.com"
ADMIN_PASSWORD = "Admin@123"


def main() -> int:
    get_settings.cache_clear()
    settings = get_settings()
    fails = 0
    with httpx.Client(base_url=BASE, timeout=30.0) as client:
        r = client.post(
            "/api/v1/admin/auth/login",
            headers={"Origin": ORIGIN},
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        print("login", r.status_code, r.json().get("role"))
        if r.status_code != 200:
            return 1

        checks = [
            "/api/v1/admin/provinces?page_size=5",
            "/api/v1/admin/district-types?page_size=5",
            "/api/v1/admin/districts?page_size=5",
            "/api/v1/admin/stops?page_size=5",
            "/api/v1/admin/buses?page_size=5",
            "/api/v1/admin/bus-services?page_size=5",
            "/api/v1/admin/routes?page_size=5",
            "/api/v1/admin/trips?page_size=5",
            "/api/v1/admin/trip-blocks?page_size=5",
            "/api/v1/admin/surcharges?page_size=5",
            "/api/v1/admin/web-profiles",
            "/api/v1/admin/menus",
            "/api/v1/admin/dashboard/stats",
            "/api/v1/admin/options/provinces?q=ha",
        ]
        for path in checks:
            r = client.get(path)
            ok = r.status_code == 200
            summary = ""
            if ok:
                body = r.json()
                if isinstance(body, dict) and "total" in body:
                    summary = f"total={body['total']} items={len(body.get('items') or [])}"
                elif isinstance(body, list):
                    summary = f"len={len(body)}"
                elif isinstance(body, dict) and "results" in body:
                    summary = f"results={len(body['results'])}"
                elif isinstance(body, dict) and "pending_total" in body:
                    summary = f"pending={body['pending_total']} revenue={body['total_revenue']}"
            else:
                fails += 1
                summary = r.text[:120]
            print(("OK" if ok else "FAIL"), path, summary)

        # reorder incomplete -> 422
        r = client.post(
            "/api/v1/admin/provinces/reorder",
            headers={"Origin": ORIGIN},
            json={"ids": [1]},
        )
        print("reorder_incomplete", r.status_code, r.json().get("detail"))
        if r.status_code != 422:
            fails += 1

    print("failures", fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
