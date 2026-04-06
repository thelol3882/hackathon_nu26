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
    # API Gateway does NOT connect to TimescaleDB — all telemetry queries
    # go through the Analytics Service via gRPC.
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

    # --- Analytics Service (gRPC) ---
    # All telemetry, alert, and health queries go through this service.
    # It is the single reader of TimescaleDB.
    analytics_grpc_target: str = "analytics-service:50051"
    analytics_grpc_timeout: float = 5.0

    # --- Report Service (gRPC) ---
    # Report status, listing, and downloads go through this service.
    report_grpc_target: str = "report-service:50052"
    report_grpc_timeout: float = 10.0

    # --- Simulator (HTTP) ---
    # The dashboard's "Operator" controls (create / update / delete
    # locomotives in the running simulation) are proxied through this
    # gateway via plain HTTP. Simulator itself is internal-only.
    simulator_http_url: str = "http://simulator:8000"
    simulator_http_timeout: float = 5.0

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
