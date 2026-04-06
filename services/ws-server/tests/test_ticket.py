"""Tests for shared.ws_ticket creation and validation."""

from unittest.mock import AsyncMock

import pytest

from shared.ws_ticket import WS_TICKET_PREFIX, create_ticket, validate_ticket


@pytest.mark.asyncio
async def test_create_and_validate_roundtrip():
    mock_redis = AsyncMock()

    stored = {}

    async def mock_set(key, value, ex=None):
        stored[key] = value

    async def mock_getdel(key):
        return stored.pop(key, None)

    mock_redis.set = mock_set
    mock_redis.getdel = mock_getdel

    ticket = await create_ticket(mock_redis, user_id="user-123", role="operator")
    assert ticket

    result = await validate_ticket(mock_redis, ticket)
    assert result is not None
    assert result["user_id"] == "user-123"
    assert result["role"] == "operator"


@pytest.mark.asyncio
async def test_ticket_single_use():
    # GETDEL should consume the ticket on first validate.
    mock_redis = AsyncMock()
    stored = {}

    async def mock_set(key, value, ex=None):
        stored[key] = value

    async def mock_getdel(key):
        return stored.pop(key, None)

    mock_redis.set = mock_set
    mock_redis.getdel = mock_getdel

    ticket = await create_ticket(mock_redis, user_id="user-123", role="operator")

    first = await validate_ticket(mock_redis, ticket)
    assert first is not None

    second = await validate_ticket(mock_redis, ticket)
    assert second is None


@pytest.mark.asyncio
async def test_invalid_ticket():
    mock_redis = AsyncMock()
    mock_redis.getdel = AsyncMock(return_value=None)

    result = await validate_ticket(mock_redis, "non-existent-ticket")
    assert result is None
    mock_redis.getdel.assert_called_once_with(f"{WS_TICKET_PREFIX}:non-existent-ticket")
