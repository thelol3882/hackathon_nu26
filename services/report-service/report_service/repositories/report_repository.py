"""Report repository — PostgreSQL only."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from report_service.models.report_entity import Report


async def create(session: AsyncSession, entity: Report) -> Report:
    session.add(entity)
    await session.commit()
    await session.refresh(entity)
    return entity


async def find_by_id(session: AsyncSession, report_id: str) -> Report | None:
    result = await session.execute(select(Report).where(Report.id == report_id))
    return result.scalar_one_or_none()


async def update_status(session: AsyncSession, report_id, status: str, data: dict | None = None) -> None:
    values: dict = {"status": status}
    if data is not None:
        values["data"] = data
    await session.execute(update(Report).where(Report.id == report_id).values(**values))
    await session.commit()
