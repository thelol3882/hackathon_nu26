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

    # --- TimescaleDB / PostgreSQL ---
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "telemetry"
    db_password: str = "changeme"
    db_name: str = "locomotive_telemetry"
    db_pool_min: int = 5
    db_pool_max: int = 20

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
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
    ws_max_connections: int = 100


@lru_cache
def get_settings() -> GatewaySettings:
    return GatewaySettings()
