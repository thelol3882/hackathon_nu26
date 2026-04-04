"""Fleet-wide aggregation and utilization statistics."""

import asyncpg


async def get_fleet_summary(pool: asyncpg.Pool) -> dict:
    """Aggregate fleet-wide statistics."""
    # TODO: implement TimescaleDB continuous aggregate queries
    return {
        "total_locomotives": 0,
        "active": 0,
        "idle": 0,
        "maintenance": 0,
        "avg_health_score": 0.0,
    }


async def get_utilization_stats(
    pool: asyncpg.Pool, locomotive_id: str | None = None
) -> dict:
    """Calculate utilization rates."""
    # TODO: implement
    return {
        "utilization_rate": 0.0,
        "avg_daily_hours": 0.0,
        "total_distance_km": 0.0,
    }
