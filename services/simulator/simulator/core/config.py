from pydantic_settings import BaseSettings


class SimulatorSettings(BaseSettings):
    model_config = {"env_prefix": "SIMULATOR_"}

    processor_url: str = "http://processor:8001"
    gateway_url: str = "http://api-gateway:8000"
    fleet_size: int = 1700
    tick_interval: float = 1.0  # seconds between ticks
    batch_size: int = 100  # locomotives per batch POST
    burst_multiplier: float = 1.0  # ×10 for highload
    scenario: str = "normal"  # normal | highload | degradation | emergency | aess
    seed: int = 42
    log_level: str = "INFO"


settings = SimulatorSettings()
