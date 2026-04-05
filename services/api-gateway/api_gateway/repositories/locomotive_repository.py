"""Locomotive repository — PostgreSQL only."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.models.locomotive_entity import Locomotive


def _apply_filters(stmt, *, search: str | None = None, model: str | None = None):
    if model:
        stmt = stmt.where(Locomotive.model.ilike(f"{model}%"))
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Locomotive.serial_number.ilike(pattern),
                Locomotive.model.ilike(pattern),
            )
        )
    return stmt


async def find_many(
    session: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 50,
    search: str | None = None,
    model: str | None = None,
) -> list[Locomotive]:
    base = select(Locomotive)
    base = _apply_filters(base, search=search, model=model)
    result = await session.execute(base.order_by(Locomotive.serial_number).offset(offset).limit(limit))
    return list(result.scalars().all())


async def find_by_id(session: AsyncSession, locomotive_id: str) -> Locomotive | None:
    result = await session.execute(select(Locomotive).where(Locomotive.id == locomotive_id))
    return result.scalar_one_or_none()


async def create(session: AsyncSession, entity: Locomotive) -> Locomotive:
    session.add(entity)
    await session.commit()
    await session.refresh(entity)
    return entity


async def get_fleet_ids(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(Locomotive.id, Locomotive.model).order_by(Locomotive.serial_number))
    return [{"id": str(row.id), "model": row.model} for row in result.all()]


async def count(
    session: AsyncSession,
    *,
    search: str | None = None,
    model: str | None = None,
) -> int:
    base = select(Locomotive)
    base = _apply_filters(base, search=search, model=model)
    result = await session.execute(select(func.count()).select_from(base.subquery()))
    return result.scalar_one()
