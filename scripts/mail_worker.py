"""Poll mail_jobs and send via Gmail SMTP."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal

from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError

from app.core.config import get_settings
from app.infrastructure.mail import mail_queue
from app.infrastructure.persistence.session import AsyncSessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("mail_worker")

_stop = False


def _handle_stop(*_args: object) -> None:
    global _stop
    _stop = True
    logger.info("Stop requested — finishing current cycle")


async def run_worker(*, sleep_seconds: float, once: bool) -> None:
    settings = get_settings()
    logger.info(
        "Mail worker started (inline=%s max_attempts=%s)",
        settings.mail_queue_inline,
        settings.mail_max_attempts,
    )
    while not _stop:
        claimed = False
        try:
            async with AsyncSessionLocal() as session:
                claimed = await mail_queue.process_one_available(
                    session, settings=settings
                )
        except (ProgrammingError, OperationalError) as exc:
            # Schema not ready yet (api still migrating) or brief DB blip —
            # keep process alive instead of Coolify restart loop.
            logger.warning("Mail queue DB not ready yet: %s", exc)
            await asyncio.sleep(max(sleep_seconds, 5.0))
            if once:
                break
            continue
        except SQLAlchemyError:
            logger.exception("Unexpected SQLAlchemy error in mail worker")
            await asyncio.sleep(max(sleep_seconds, 5.0))
            if once:
                break
            continue
        if once:
            break
        if not claimed:
            await asyncio.sleep(sleep_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Process durable mail_jobs via SMTP")
    parser.add_argument(
        "--sleep",
        type=float,
        default=2.0,
        help="Seconds to sleep when the queue is empty (default: 2)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one job then exit",
    )
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _handle_stop)
    try:
        signal.signal(signal.SIGTERM, _handle_stop)
    except (AttributeError, ValueError):
        pass

    asyncio.run(run_worker(sleep_seconds=args.sleep, once=args.once))


if __name__ == "__main__":
    main()
