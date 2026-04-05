"""Shared fixtures for analytics-service tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class _FakeSettings:
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "test"
    db_password: str = "test"
    db_name: str = "test"
    db_pool_min: int = 1
    db_pool_max: int = 2
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    grpc_port: int = 50051
    http_port: int = 8020
    service_name: str = "analytics-service-test"


@pytest.fixture
def _patch_settings():
    with patch("analytics.core.config.get_settings", return_value=_FakeSettings()):
        yield
