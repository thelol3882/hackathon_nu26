from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GATEWAY_",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "locomotive-api-gateway"
    debug: bool = False

    # --- Application database (PostgreSQL) ---
    # Small CRUD tables: users, locomotives, reports, health config.
    # Standard ORM operations with JOINs between business entities.
    app_db_host: str = "postgres"
    app_db_port: int = 5432
    app_db_user: str = "locomotive_app"
    app_db_password: str = "changeme"
    app_db_name: str = "locomotive_app"
    app_db_pool_min: int = 3
    app_db_pool_max: int = 10

    @property
    def app_database_url(self) -> str:
        return (
            f"postgresql://{self.app_db_user}:{self.app_db_password}"
            f"@{self.app_db_host}:{self.app_db_port}/{self.app_db_name}"
        )

    # --- Telemetry database (TimescaleDB) ---
    # Huge time-series tables: raw_telemetry, alert_events, health_snapshots,
    # continuous aggregates. Read-only from API Gateway (DB Writer handles writes).
    ts_db_host: str = "timescaledb"
    ts_db_port: int = 5432
    ts_db_user: str = "telemetry"
    ts_db_password: str = "changeme"
    ts_db_name: str = "locomotive_telemetry"
    ts_db_pool_min: int = 3
    ts_db_pool_max: int = 10

    @property
    def ts_database_url(self) -> str:
        return (
            f"postgresql://{self.ts_db_user}:{self.ts_db_password}"
            f"@{self.ts_db_host}:{self.ts_db_port}/{self.ts_db_name}"
        )

    # --- Redis ---
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # --- RabbitMQ ---
    rabbitmq_url: str = "amqp://locomotive:changeme@rabbitmq:5672/"

    # --- JWT Auth ---
    jwt_secret: str = "super-secret-change-me"
    jwt_expiry_minutes: int = 60

    # --- Gateway-specific ---
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> GatewaySettings:
    return GatewaySettings()
