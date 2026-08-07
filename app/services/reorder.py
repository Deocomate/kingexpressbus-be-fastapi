"""Full-list priority reorder (DESC: first id gets highest priority)."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase


async def reorder_full_table(
    db: AsyncSession,
    model: type,
    ids: list[int],
    *,
    priority_attr: str = "priority",
) -> None:
    """Reject unless ids are a permutation of the entire table."""
    if not ids:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Không có dữ liệu để sắp xếp.",
        )
    if len(ids) != len(set(ids)):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Danh sách sắp xếp không khớp toàn bộ bảng.",
        )

    valid = await db.scalar(select(func.count()).select_from(model).where(model.id.in_(ids)))
    total = await db.scalar(select(func.count()).select_from(model))
    if valid != len(ids) or valid != total:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Danh sách sắp xếp không khớp toàn bộ bảng.",
        )

    n = len(ids)
    for index, row_id in enumerate(ids):
        await db.execute(
            update(model)
            .where(model.id == row_id)
            .values(**{priority_attr: n - index})
        )
    await db.commit()


async def reorder_scoped(
    db: AsyncSession,
    model: type,
    ids: list[int],
    *,
    scope_column: str,
    scope_value: int,
    priority_attr: str = "priority",
) -> None:
    """Reorder within a parent scope (e.g. route_stops for one route)."""
    if not ids:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Không có dữ liệu để sắp xếp.",
        )
    col = getattr(model, scope_column)
    valid = await db.scalar(
        select(func.count()).select_from(model).where(col == scope_value, model.id.in_(ids))
    )
    total = await db.scalar(select(func.count()).select_from(model).where(col == scope_value))
    if valid != len(ids) or valid != total or len(ids) != len(set(ids)):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Danh sách sắp xếp không khớp toàn bộ phạm vi.",
        )
    n = len(ids)
    for index, row_id in enumerate(ids):
        await db.execute(
            update(model)
            .where(model.id == row_id, col == scope_value)
            .values(**{priority_attr: n - index})
        )
    await db.commit()
