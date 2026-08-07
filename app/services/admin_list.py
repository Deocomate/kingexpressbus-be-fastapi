"""Pagination + slug helpers for admin list endpoints."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value.lower())
    value = re.sub(r"[-\s]+", "-", value).strip("-")
    return value or "item"


async def paginate(
    db: AsyncSession,
    stmt: Select[Any],
    *,
    page: int = 1,
    page_size: int = 25,
    as_rows: bool = False,
) -> tuple[list[Any], int]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int(await db.scalar(count_stmt) or 0)
    result = await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    # Multi-column selects (joined labels) need full rows; scalars() only returns col 0.
    if as_rows:
        items = list(result.all())
    else:
        try:
            items = list(result.scalars().unique().all())
        except Exception:  # noqa: BLE001
            items = list(result.all())
    return items, total
