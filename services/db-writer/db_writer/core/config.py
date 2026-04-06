from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class DbWriterSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DB_WRITER_",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "locomotive-db-writer"
    debug: bool = False

    # --- TimescaleDB / PostgreSQL ---
    db_host: str = "timescaledb"
    db_port: int = 5432
    db_user: str = "telemetry"
    db_password: str = "changeme"
    db_name: str = "locomotive_telemetry"
    db_pool_min: int = 5
    db_pool_max: int = 30  # writer needs more connections for bulk inserts

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    # --- Redis ---
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # --- Worker ---
    consumer_name: str = "writer-1"  # unique per replica
    flush_interval: float = 0.5  # seconds between flushes

    # --- Retention ---
    retention_telemetry_hours: int = 72
    retention_alerts_hours: int = 168
    retention_health_hours: int = 168
    compression_after_hours: int = 1

    # --- Metrics ---
    metrics_port: int = 8004


@lru_cache
def get_settings() -> DbWriterSettings:
    return DbWriterSettings()
