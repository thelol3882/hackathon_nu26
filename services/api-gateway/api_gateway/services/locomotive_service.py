"""CRUD operations for the locomotive registry."""

import asyncpg

from shared.schemas.locomotive import LocomotiveCreate, LocomotiveRead


async def create_locomotive(
    pool: asyncpg.Pool, data: LocomotiveCreate
) -> LocomotiveRead:
    """Register a new locomotive."""
    # TODO: implement INSERT
    raise NotImplementedError


async def get_locomotive(pool: asyncpg.Pool, locomotive_id: str) -> LocomotiveRead:
    """Fetch a single locomotive by ID."""
    # TODO: implement SELECT
    raise NotImplementedError


async def list_locomotives(
    pool: asyncpg.Pool, offset: int = 0, limit: int = 50
) -> list[LocomotiveRead]:
    """List locomotives with pagination."""
    # TODO: implement SELECT with pagination
    return []
