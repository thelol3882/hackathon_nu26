"""Seed default data on first startup: admin user + locomotive fleet."""

from __future__ import annotations

import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.core.auth import hash_password
from api_gateway.models.locomotive_entity import Locomotive
from api_gateway.models.user_entity import User
from shared.enums import LocomotiveType
from shared.observability import get_logger

logger = get_logger(__name__)

# Manufacturer metadata for realistic seeding
_LOCO_META = {
    LocomotiveType.TE33A: {
        "model": "TE33A Evolution",
        "manufacturer": "GE Transportation (Wabtec)",
        "year_range": (2018, 2024),
    },
    LocomotiveType.KZ8A: {
        "model": "KZ8A Prima II",
        "manufacturer": "Alstom / EKZ",
        "year_range": (2019, 2025),
    },
}


async def seed_admin_user(session: AsyncSession) -> None:
    """Create a default admin user if no users exist."""
    result = await session.execute(select(func.count()).select_from(User))
    count = result.scalar_one()
    if count > 0:
        return

    admin = User(
        username="admin",
        hashed_password=hash_password("admin"),
        role="admin",
    )
    operator = User(
        username="operator",
        hashed_password=hash_password("operator"),
        role="operator",
    )
    session.add_all([admin, operator])
    await session.commit()
    logger.info("Seeded default users", users=["admin", "operator"])


async def seed_locomotives(session: AsyncSession, fleet_size: int = 1700) -> None:
    """Create locomotive records matching the simulator fleet size if table is empty."""
    result = await session.execute(select(func.count()).select_from(Locomotive))
    count = result.scalar_one()
    if count > 0:
        return

    te33a_count = int(fleet_size * 0.6)
    locos: list[Locomotive] = []

    for i in range(fleet_size):
        loco_type = LocomotiveType.TE33A if i < te33a_count else LocomotiveType.KZ8A
        meta = _LOCO_META[loco_type]

        locos.append(
            Locomotive(
                serial_number=f"{loco_type.value}-{i + 1:04d}",
                model=meta["model"],
                manufacturer=meta["manufacturer"],
                year_manufactured=random.randint(*meta["year_range"]),  # noqa: S311
                status="active",
            )
        )

    session.add_all(locos)
    await session.commit()
    logger.info("Seeded locomotive fleet", count=fleet_size, te33a=te33a_count, kz8a=fleet_size - te33a_count)
