"""Report repository — PostgreSQL only."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.models.report_entity import Report


async def create(session: AsyncSession, entity: Report) -> Report:
    session.add(entity)
    await session.commit()
    await session.refresh(entity)
    return entity


async def find_by_id(session: AsyncSession, report_id: str) -> Report | None:
    result = await session.execute(select(Report).where(Report.id == report_id))
    return result.scalar_one_or_none()


async def find_many(
    session: AsyncSession,
    *,
    locomotive_id: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> list[Report]:
    stmt = select(Report).order_by(Report.created_at.desc())
    if locomotive_id:
        stmt = stmt.where(Report.locomotive_id == locomotive_id)
    if status:
        stmt = stmt.where(Report.status == status)
    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())
