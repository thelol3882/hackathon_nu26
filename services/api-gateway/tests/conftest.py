"""Shared fixtures for api-gateway tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _FakeSettings:
    jwt_secret: str = "test-secret-key-for-testing-32bytes!"
    jwt_expiry_minutes: int = 60


@pytest.fixture
def mock_settings():
    """Return a fake GatewaySettings with known JWT config."""
    return _FakeSettings()


@pytest.fixture
def _patch_settings(mock_settings):
    """Automatically patch get_settings for every test that requests it."""
    with patch("api_gateway.core.config.get_settings", return_value=mock_settings):
        yield mock_settings


@pytest.fixture
def mock_session():
    """AsyncSession mock with common async methods."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_redis():
    """Async Redis client mock."""
    r = AsyncMock()
    r.pubsub = MagicMock(return_value=AsyncMock())
    return r
