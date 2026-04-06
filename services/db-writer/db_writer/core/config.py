from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class DbWriterSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DB_WRITER_",
        case_sensitive=False,
    )

    app_name: str = "locomotive-db-writer"
    debug: bool = False

    db_host: str = "timescaledb"
    db_port: int = 5432
    db_user: str = "telemetry"
    db_password: str = "changeme"
    db_name: str = "locomotive_telemetry"
    db_pool_min: int = 10
    # Writer needs more connections for parallel bulk inserts.
    db_pool_max: int = 40

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Must be unique per replica.
    consumer_name: str = "writer-1"

    # Telemetry is the hot path and scales with parallel COPY workers.
    writer_workers_telemetry: int = 3
    writer_workers_alerts: int = 1
    writer_workers_health: int = 1

    # Bounds per-flush latency so XACK cadence keeps the Redis backlog in check.
    rows_per_flush: int = 5000

    # Bounded reader→worker queue provides backpressure.
    queue_maxsize: int = 4

    retention_telemetry_hours: int = 72
    retention_alerts_hours: int = 168
    retention_health_hours: int = 168
    compression_after_hours: int = 1

    metrics_port: int = 8004


@lru_cache
def get_settings() -> DbWriterSettings:
    return DbWriterSettings()
