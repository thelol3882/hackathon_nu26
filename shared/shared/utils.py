"""Shared utilities used across all services."""

import uuid

from uuid_utils import uuid7


def generate_id() -> uuid.UUID:
    """Generate a UUIDv7 (time-sortable; friendly to Postgres B-tree indexes)."""
    return uuid.UUID(bytes=uuid7().bytes)
