"""Live mail verification: SMTP + queue + optional booking API trigger.

Run from backend root with .venv active:
  python scripts/dev/mail_live_probe.py
  python scripts/dev/mail_live_probe.py --api   # also POST /api/v1/bookings (needs uvicorn)
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, timedelta

from sqlalchemy import text

from app.core.config import get_settings
from app.infrastructure.mail.mail import queue_booking_mail
from app.infrastructure.mail.mail_queue import process_one_available
from app.infrastructure.mail.mail_sender import SmtpMailSender
from app.infrastructure.persistence.session import AsyncSessionLocal


async def probe_smtp() -> None:
    settings = get_settings()
    print("=== 1) SMTP credentials ===")
    print(f"host={settings.mail_host}:{settings.mail_port}")
    print(f"user={settings.mail_username}")
    print(f"from={settings.mail_from}")
    print(f"admin={settings.admin_notify_email}")
    print(f"password_set={bool(settings.mail_password)} len={len(settings.mail_password)}")
    if not settings.mail_username or not settings.mail_password:
        raise RuntimeError("MAIL_USERNAME / MAIL_PASSWORD missing in .env")

    to = [settings.admin_notify_email or settings.mail_from]
    sender = SmtpMailSender(settings)
    subject = "[KEB probe] SMTP live test"
    html = (
        "<p>King Express Bus FastAPI mail probe.</p>"
        "<p>If you received this, Gmail SMTP credentials work.</p>"
    )
    print(f"sending to={to} ...")
    await sender.send(to=to, subject=subject, html=html)
    print("SMTP send: OK")


async def probe_queue_existing_booking() -> int | None:
    settings = get_settings()
    print("\n=== 2) Queue path via existing booking ===")
    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(
                text(
                    """
                    select b.id, b.booking_code, b.customer_email
                    from bookings b
                    where b.customer_email is not null
                      and b.customer_email <> ''
                    order by b.id desc
                    limit 1
                    """
                )
            )
        ).mappings().first()
        if not row:
            print("No booking with customer_email found — skip queue probe")
            return None

        booking_id = int(row["id"])
        print(
            f"using booking id={booking_id} code={row['booking_code']} "
            f"email={row['customer_email']}"
        )
        before = (
            await db.execute(text("select count(*) from mail_jobs"))
        ).scalar()
        ok = await queue_booking_mail(
            db,
            booking_id=booking_id,
            kind="confirmation",
            settings=settings,
        )
        # Inline processing can miss a just-committed row in some MySQL
        # session/timezone edge cases — drain any leftover once more.
        drained = await process_one_available(db, settings=settings)
        after = (
            await db.execute(text("select count(*) from mail_jobs"))
        ).scalar()
        pending = (
            await db.execute(
                text(
                    "select id, attempts, reserved_at, last_error "
                    "from mail_jobs order by id desc limit 5"
                )
            )
        ).mappings().all()
        failed = (
            await db.execute(
                text(
                    "select count(*) from failed_mail_jobs "
                    "where failed_at >= (utc_timestamp() - interval 5 minute)"
                )
            )
        ).scalar()
        print(f"queue_booking_mail ok={ok} drained_extra={drained}")
        print(f"mail_jobs count before={before} after={after}")
        print(f"pending_tail={list(pending)}")
        print(f"failed_mail_jobs last 5m={failed}")
        if not ok:
            raise RuntimeError("queue_booking_mail returned False")
        if after and int(after) > 0:
            raise RuntimeError(
                f"mail_jobs still pending after send: {list(pending)}"
            )
        if failed and int(failed) > 0:
            raise RuntimeError("new failed_mail_jobs detected after send")
        print("Queue + SMTP inline: OK")
        return booking_id


async def probe_api_create_booking() -> None:
    import httpx

    settings = get_settings()
    print("\n=== 3) Public POST /api/v1/bookings (triggers confirmation mail) ===")

    async with AsyncSessionLocal() as db:
        pair = (
            await db.execute(
                text(
                    """
                    select t.id as trip_id,
                           t.price,
                           r.id as route_id,
                           (
                             select s.id from stops s
                             where s.province_id = r.province_start_id
                             order by s.id limit 1
                           ) as pickup_stop_id,
                           (
                             select s.id from stops s
                             where s.province_id = r.province_end_id
                             order by s.id limit 1
                           ) as dropoff_stop_id
                    from trips t
                    join routes r on r.id = t.route_id
                    where t.is_active = 1
                    limit 1
                    """
                )
            )
        ).mappings().first()
        if not pair or not pair["pickup_stop_id"] or not pair["dropoff_stop_id"]:
            raise RuntimeError("No active trip+stops available for booking probe")

        # Get authoritative price from public price endpoint if possible
        trip_id = int(pair["trip_id"])
        pickup = int(pair["pickup_stop_id"])
        dropoff = int(pair["dropoff_stop_id"])
        travel = (date.today() + timedelta(days=7)).isoformat()

    base = "http://127.0.0.1:8000"
    async with httpx.AsyncClient(base_url=base, timeout=30.0) as client:
        health = await client.get("/health")
        if health.status_code != 200:
            raise RuntimeError(
                f"API not up at {base} (health={health.status_code}). "
                "Start: uvicorn app.main:app --reload --port 8000"
            )

        price_r = await client.get(
            f"/api/v1/public/trips/{trip_id}/price",
            params={"date": travel},
        )
        if price_r.status_code == 200:
            data = price_r.json()
            total = int(
                data.get("total_price")
                or data.get("final_total")
                or data.get("amount")
                or 0
            )
            if not total and "final_unit_price" in data:
                total = int(data["final_unit_price"])
        else:
            print(f"price endpoint status={price_r.status_code} body={price_r.text[:200]}")
            total = int(pair["price"] or 0)

        if total <= 0:
            total = int(pair["price"] or 100000)

        payload = {
            "trip_id": trip_id,
            "booking_date": travel,
            "quantity": 1,
            "customer_name": "Mail Probe",
            "customer_phone": "0900000099",
            "customer_email": settings.admin_notify_email,
            "dropoff_stop_id": dropoff,
            "pickup_stop_id": pickup,
            "total_price": total,
            "payment_method": "cash_on_pickup",
            "notes": "mail live probe — safe to ignore",
        }
        print(f"POST /api/v1/bookings payload trip={trip_id} total={total}")
        r = await client.post("/api/v1/bookings", json=payload)
        print(f"status={r.status_code}")
        print(f"body={r.text[:500]}")
        if r.status_code not in (200, 201):
            raise RuntimeError(f"create booking failed: {r.status_code}")
        # Give BackgroundTasks a moment to enqueue + SMTP
        await asyncio.sleep(3)
        print("API booking create: OK (check inbox for confirmation)")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api",
        action="store_true",
        help="Also hit POST /api/v1/bookings (requires running uvicorn)",
    )
    args = parser.parse_args()
    try:
        await probe_smtp()
        await probe_queue_existing_booking()
        if args.api:
            await probe_api_create_booking()
        print("\nALL MAIL PROBES PASSED")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"\nFAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
