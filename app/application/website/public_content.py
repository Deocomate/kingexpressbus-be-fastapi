"""Website / public CMS use cases (return ORM / plain data — map in presentation)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.shared.errors import NotFoundError
from app.infrastructure.persistence.models import Menu, WebProfile


async def get_default_web_profile(db: AsyncSession) -> WebProfile:
    result = await db.execute(
        select(WebProfile).where(WebProfile.is_default.is_(True)).limit(1)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        result = await db.execute(select(WebProfile).limit(1))
        profile = result.scalar_one_or_none()
    if profile is None:
        raise NotFoundError("Web profile not found")
    return profile


async def list_menus(db: AsyncSession) -> list[Menu]:
    result = await db.execute(select(Menu))
    return list(result.scalars().all())
