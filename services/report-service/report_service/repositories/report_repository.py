from __future__ import annotations

from sqlalchemy import func, select, update
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


async def find_many(
    session: AsyncSession,
    *,
    locomotive_id: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Report], int]:
    """Return (reports, total_count) with optional filters."""
    q = select(Report)
    count_q = select(func.count()).select_from(Report)

    if locomotive_id:
        q = q.where(Report.locomotive_id == locomotive_id)
        count_q = count_q.where(Report.locomotive_id == locomotive_id)
    if status:
        q = q.where(Report.status == status)
        count_q = count_q.where(Report.status == status)

    total = (await session.execute(count_q)).scalar_one()
    q = q.order_by(Report.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(q)
    return list(result.scalars().all()), total


async def update_status(session: AsyncSession, report_id, status: str, data: dict | None = None) -> None:
    values: dict = {"status": status}
    if data is not None:
        values["data"] = data
    await session.execute(update(Report).where(Report.id == report_id).values(**values))
    await session.commit()
