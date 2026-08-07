"""Shared helper for the locations resource group (slug uniqueness)."""

from __future__ import annotations

from sqlalchemy import func, select

from app.core.deps import DbSession
from app.services.admin_list import slugify


async def unique_slug(db: DbSession, model, base: str, exclude_id: int | None = None) -> str:
    slug = slugify(base)
    candidate = slug
    n = 2
    while True:
        stmt = select(func.count()).select_from(model).where(model.slug == candidate)
        if exclude_id is not None:
            stmt = stmt.where(model.id != exclude_id)
        if int(await db.scalar(stmt) or 0) == 0:
            return candidate
        candidate = f"{slug}-{n}"
        n += 1
