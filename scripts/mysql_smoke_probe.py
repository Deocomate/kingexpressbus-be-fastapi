"""MySQL smoke probe — auth + trip search readiness."""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings


async def main() -> int:
    settings = get_settings()
    print(
        f"DB {settings.db_username}@{settings.db_host}:{settings.db_port}/"
        f"{settings.db_database}"
    )
    eng = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with eng.connect() as conn:
            db = (await conn.execute(text("select database()"))).scalar()
            users = (await conn.execute(text("select count(*) from users"))).scalar()
            trips = (await conn.execute(text("select count(*) from trips"))).scalar()
            routes = (await conn.execute(text("select count(*) from routes"))).scalar()
            admins = (
                await conn.execute(
                    text(
                        "select id, email, role, "
                        "left(password, 7) as hash_prefix "
                        "from users where role = 'admin' limit 5"
                    )
                )
            ).all()
            customers = (
                await conn.execute(
                    text(
                        "select id, email, role "
                        "from users where role = 'customer' "
                        "and email is not null limit 3"
                    )
                )
            ).all()
            provinces = (
                await conn.execute(
                    text(
                        "select id, name from provinces "
                        "order by priority desc, name asc limit 8"
                    )
                )
            ).all()
            pairs = (
                await conn.execute(
                    text(
                        """
                        select r.province_start_id, r.province_end_id, count(*) as c
                        from trips t
                        join routes r on t.route_id = r.id
                        where t.is_active = 1
                        group by r.province_start_id, r.province_end_id
                        order by c desc
                        limit 5
                        """
                    )
                )
            ).all()
            print(f"database={db}")
            print(f"counts users={users} trips={trips} routes={routes}")
            print(f"admins={admins}")
            print(f"customers={customers}")
            print(f"provinces={provinces}")
            print(f"search_pairs={pairs}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        await eng.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
