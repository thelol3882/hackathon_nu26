"""Historical telemetry queries against TimescaleDB."""

import asyncpg

from api_gateway.models.query_params import FilterParams


async def query_telemetry(pool: asyncpg.Pool, filters: FilterParams) -> list[dict]:
    """Query historical telemetry with optional filters."""
    # TODO: implement TimescaleDB query with time_bucket
    return []
