"""CLI for additive seed updates (production-safe).

Usage::

    python -m scripts.seeds.apply --list
    python -m scripts.seeds.apply 20260808_hotels_tours_menus
    python -m scripts.seeds.apply --all
    python -m scripts.seeds.apply 20260808_hotels_tours_menus --update
    python -m scripts.seeds.apply 20260808_hotels_tours_menus --dry-run

Never truncates. Prefer this on production instead of ``scripts/seed.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Allow ``python scripts/seeds/apply.py`` as well as ``-m``.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.core.config import get_settings
from app.infrastructure.persistence.session import engine
from scripts.seeds.registry import UPDATES, get_update


def _print_list() -> None:
    print("Available additive seed updates:")
    for mod in UPDATES:
        print(f"  {mod.NAME}")
        print(f"    {mod.DESCRIPTION}")


def _format_result(name: str, result: dict) -> None:
    print(f"\n[{name}]")
    print(json.dumps(result, indent=2, ensure_ascii=False))


async def _run(
    names: list[str],
    *,
    update_existing: bool,
    dry_run: bool,
) -> int:
    settings = get_settings()
    print(
        f"APP_ENV={settings.app_env!r} DB={settings.db_database} "
        f"host={settings.db_host} dry_run={dry_run} update={update_existing}"
    )

    try:
        async with engine.begin() as conn:
            for name in names:
                mod = get_update(name)
                result = await mod.apply(
                    conn,
                    update_existing=update_existing,
                    dry_run=dry_run,
                )
                _format_result(name, result)
    finally:
        await engine.dispose()

    if dry_run:
        print("\nDry-run only - no rows written.")
    else:
        print("\nAdditive seed apply complete.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Apply additive seed updates (insert-missing by slug/url). "
            "Safe for production; does not truncate."
        )
    )
    parser.add_argument(
        "names",
        nargs="*",
        help="Update module name(s), e.g. 20260808_hotels_tours_menus",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Apply every registered update in order.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available updates and exit.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Also overwrite fields on rows that already exist (by natural key).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count inserts/updates without writing.",
    )
    args = parser.parse_args()

    if args.list:
        _print_list()
        raise SystemExit(0)

    if args.all:
        names = [m.NAME for m in UPDATES]
    else:
        names = list(args.names)

    if not names:
        parser.error("Provide update name(s), or use --all / --list.")

    try:
        for name in names:
            get_update(name)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc

    raise SystemExit(
        asyncio.run(
            _run(names, update_existing=args.update, dry_run=args.dry_run)
        )
    )


if __name__ == "__main__":
    main()
