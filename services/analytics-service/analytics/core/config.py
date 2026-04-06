"""Analytics Service configuration.

This service is the SINGLE READER of TimescaleDB. It exposes data
via gRPC to API Gateway, Report Service, and any future consumers.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AnalyticsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ANALYTICS_",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "locomotive-analytics-service"
    debug: bool = False
    service_name: str = "analytics-service"

    # --- TimescaleDB (READ ONLY) ---
    # This service never writes to the database.
    # DB Writer handles all inserts.
    db_host: str = "timescaledb"
    db_port: int = 5432
    db_user: str = "telemetry"
    db_password: str = "changeme"
    db_name: str = "locomotive_telemetry"
    db_pool_min: int = 5
    db_pool_max: int = 20

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    # --- Redis (for health index cache) ---
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # --- gRPC server ---
    grpc_port: int = 50051

    # --- HTTP server (Prometheus /metrics and /health only) ---
    http_port: int = 8020


@lru_cache
def get_settings() -> AnalyticsSettings:
    return AnalyticsSettings()
