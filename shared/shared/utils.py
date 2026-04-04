"""Shared utilities used across all services."""

import uuid

from uuid_utils import uuid7


def generate_id() -> uuid.UUID:
    """Generate a UUIDv7 (time-sortable).

    Better than UUIDv4 for PostgreSQL B-tree indexes:
    monotonically increasing, no random page splits.
    """
    return uuid.UUID(bytes=uuid7().bytes)
