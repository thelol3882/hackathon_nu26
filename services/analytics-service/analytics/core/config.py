"""Analytics Service config. Sole reader of TimescaleDB; exposes data via gRPC."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AnalyticsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ANALYTICS_",
        case_sensitive=False,
    )

    app_name: str = "locomotive-analytics-service"
    debug: bool = False
    service_name: str = "analytics-service"

    # TimescaleDB is read-only here; DB Writer owns all inserts.
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

    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    grpc_port: int = 50051
    http_port: int = 8020


@lru_cache
def get_settings() -> AnalyticsSettings:
    return AnalyticsSettings()
