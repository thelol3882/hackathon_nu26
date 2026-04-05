"""
Shared constants: sensor specifications, thresholds, EMA gains, Redis channels.

Health Index formula (processor real-time):
    HI(t) = 100 - Σ W_i · ( max(0, |P̂_i - P_nom| - δ_safe) / (P_crit - P_nom) )^k
    clamped to [0, 100].
"""

from dataclasses import dataclass

from shared.enums import SensorType, ThresholdType


@dataclass(frozen=True)
class SensorSpec:
    """Per-sensor configuration for Health Index calculation."""

    weight: float  # W_i in HI formula (0–40; ≥35 for fatal params)
    p_nom: float  # nominal / target value
    delta_safe: float  # half-width of safe zone — no penalty inside
    p_crit: float  # critical threshold (normalization anchor)
    threshold_type: ThresholdType = ThresholdType.BIDIRECTIONAL
    k: float = 2.0  # penalty exponent; higher → steeper near critical
    is_aging_param: bool = False  # apply Montsinger accumulator
    montsinger_ref_temp: float = 0.0  # °C reference for aging calc

    @property
    def crit_range(self) -> float:
        """Distance from (nominal ± delta_safe) to critical for normalization."""
        return max(1e-6, abs(self.p_crit - self.p_nom) - self.delta_safe)


# ── TE33A Sensor Specs ──────────────────────────────────────────────────────
_TE33A: dict[str, SensorSpec] = {
    SensorType.DIESEL_RPM: SensorSpec(
        weight=15,
        p_nom=700,
        delta_safe=200,
        p_crit=1050,
        threshold_type=ThresholdType.UPPER_BOUND,
        k=2.0,
    ),
    # Oil pressure is cross-validated against RPM (see alert_evaluator)
    SensorType.OIL_PRESSURE: SensorSpec(
        weight=35,
        p_nom=3.5,
        delta_safe=1.0,
        p_crit=1.5,
        threshold_type=ThresholdType.LOWER_BOUND,
        k=2.0,
    ),
    SensorType.COOLANT_TEMP: SensorSpec(
        weight=20,
        p_nom=82,
        delta_safe=13,
        p_crit=95,
        threshold_type=ThresholdType.UPPER_BOUND,
        k=2.0,
    ),
    SensorType.FUEL_LEVEL: SensorSpec(
        weight=10,
        p_nom=50,
        delta_safe=40,
        p_crit=5,
        threshold_type=ThresholdType.LOWER_BOUND,
        k=1.5,
    ),
    SensorType.FUEL_RATE: SensorSpec(
        weight=10,
        p_nom=80,
        delta_safe=60,
        p_crit=200,
        threshold_type=ThresholdType.UPPER_BOUND,
        k=1.5,
    ),
    SensorType.TRACTION_MOTOR_TEMP: SensorSpec(
        weight=15,
        p_nom=85,
        delta_safe=45,
        p_crit=130,
        threshold_type=ThresholdType.UPPER_BOUND,
        k=2.0,
    ),
    SensorType.CRANKCASE_PRESSURE: SensorSpec(
        weight=40,
        p_nom=0,
        delta_safe=10,
        p_crit=50,
        threshold_type=ThresholdType.UPPER_BOUND,
        k=3.0,
    ),
    # Common params shared across both types
    SensorType.BRAKE_PIPE_PRESSURE: SensorSpec(
        weight=40,
        p_nom=5.1,
        delta_safe=0.2,
        p_crit=2.0,
        threshold_type=ThresholdType.LOWER_BOUND,
        k=3.0,
    ),
    SensorType.WHEEL_SLIP_RATIO: SensorSpec(
        weight=20,
        p_nom=0.0,
        delta_safe=0.05,
        p_crit=0.5,
        threshold_type=ThresholdType.UPPER_BOUND,
        k=2.0,
    ),
    SensorType.SPEED_ACTUAL: SensorSpec(
        weight=15,
        p_nom=60,
        delta_safe=60,
        p_crit=120,
        threshold_type=ThresholdType.UPPER_BOUND,
        k=2.0,
    ),
}

# ── KZ8A Sensor Specs ───────────────────────────────────────────────────────
_KZ8A: dict[str, SensorSpec] = {
    SensorType.CATENARY_VOLTAGE: SensorSpec(
        weight=25,
        p_nom=25_000,
        delta_safe=4_000,
        p_crit=19_000,
        threshold_type=ThresholdType.BIDIRECTIONAL,
        k=2.0,
    ),
    SensorType.PANTOGRAPH_CURRENT: SensorSpec(
        weight=15,
        p_nom=200,
        delta_safe=150,
        p_crit=400,
        threshold_type=ThresholdType.UPPER_BOUND,
        k=2.0,
    ),
    # Alstom transformer — cellulose aging doubles every 6 °C (Montsinger)
    SensorType.TRANSFORMER_TEMP: SensorSpec(
        weight=20,
        p_nom=65,
        delta_safe=15,
        p_crit=90,
        threshold_type=ThresholdType.UPPER_BOUND,
        k=2.0,
        is_aging_param=True,
        montsinger_ref_temp=65.0,
    ),
    # IGBT — semiconductor aging; critical if sustained overtemp
    SensorType.IGBT_TEMP: SensorSpec(
        weight=30,
        p_nom=57,
        delta_safe=18,
        p_crit=85,
        threshold_type=ThresholdType.UPPER_BOUND,
        k=2.0,
        is_aging_param=True,
        montsinger_ref_temp=57.0,
    ),
    SensorType.RECUPERATION_CURRENT: SensorSpec(
        weight=5,
        p_nom=100,
        delta_safe=100,
        p_crit=0,
        threshold_type=ThresholdType.LOWER_BOUND,
        k=1.0,
    ),
    SensorType.DC_LINK_VOLTAGE: SensorSpec(
        weight=20,
        p_nom=2_800,
        delta_safe=300,
        p_crit=2_000,
        threshold_type=ThresholdType.BIDIRECTIONAL,
        k=2.0,
    ),
    # Common params
    SensorType.BRAKE_PIPE_PRESSURE: SensorSpec(
        weight=40,
        p_nom=5.1,
        delta_safe=0.2,
        p_crit=2.0,
        threshold_type=ThresholdType.LOWER_BOUND,
        k=3.0,
    ),
    SensorType.WHEEL_SLIP_RATIO: SensorSpec(
        weight=20,
        p_nom=0.0,
        delta_safe=0.05,
        p_crit=0.5,
        threshold_type=ThresholdType.UPPER_BOUND,
        k=2.0,
    ),
    SensorType.SPEED_ACTUAL: SensorSpec(
        weight=15,
        p_nom=60,
        delta_safe=60,
        p_crit=120,
        threshold_type=ThresholdType.UPPER_BOUND,
        k=2.0,
    ),
}

# Public lookup: LOCO_SPECS[locomotive_type][sensor_type] -> SensorSpec
LOCO_SPECS: dict[str, dict[str, SensorSpec]] = {
    "TE33A": _TE33A,
    "KZ8A": _KZ8A,
}

# ── EMA / Kalman gain per sensor ────────────────────────────────────────────
# K in x̂_k = K·z_k + (1-K)·x̂_{k-1}
# Low K → heavy smoothing (thermal sensors, 1 Hz)
# High K → light smoothing (electrodynamic, 50 Hz)
EMA_GAINS: dict[str, float] = {
    # Thermal — slow dynamics
    SensorType.COOLANT_TEMP: 0.10,
    SensorType.TRANSFORMER_TEMP: 0.10,
    SensorType.IGBT_TEMP: 0.15,
    SensorType.TRACTION_MOTOR_TEMP: 0.10,
    # Electrodynamic / mechanical — fast dynamics
    SensorType.CATENARY_VOLTAGE: 0.30,
    SensorType.PANTOGRAPH_CURRENT: 0.30,
    SensorType.DC_LINK_VOLTAGE: 0.35,
    SensorType.WHEEL_SLIP_RATIO: 0.25,
    SensorType.DIESEL_RPM: 0.25,
    # Default fallback
    "__default__": 0.20,
}

# ── AESS (Auto Engine Start/Stop) masking for TE33A ─────────────────────────
AESS_RPM_THRESHOLD: float = 50.0  # RPM ≤ this → engine in sleep mode
AESS_MASKED_SENSORS: frozenset[str] = frozenset(
    {
        SensorType.DIESEL_RPM,
        SensorType.OIL_PRESSURE,
    }
)

# ── HI category thresholds ──────────────────────────────────────────────────
HI_CATEGORY_NORMAL = 80.0  # ≥ 80 → "Норма"
HI_CATEGORY_WARNING = 50.0  # 50–79 → "Внимание"
# < 50 → "Критично"

# ── Montsinger aging constants ───────────────────────────────────────────────
MONTSINGER_DEGREE_STEP: float = 6.0  # aging doubles every 6 °C
MONTSINGER_BASE_DAMAGE: float = 0.001  # penalty subtracted per unit of age

# ── Redis Pub/Sub channels ───────────────────────────────────────────────────
TELEMETRY_CHANNEL = "telemetry:live"
ALERT_CHANNEL = "alerts:live"
HEALTH_CHANNEL = "health:live"

# Fleet aggregation channels — published by fleet aggregator inside Analytics Service.
# Consumed by WS Server for fleet dashboard streaming.
FLEET_SUMMARY_CHANNEL = "fleet:summary"
FLEET_CHANGES_CHANNEL = "fleet:changes"

# ── Legacy — kept for report-service backward compatibility ─────────────────
DEFAULT_THRESHOLDS: dict[str, tuple[float, float]] = {
    "diesel_rpm": (0.0, 1050.0),
    "oil_pressure": (1.5, 5.0),
    "coolant_temp": (70.0, 95.0),
    "fuel_level": (5.0, 100.0),
    "fuel_rate": (10.0, 200.0),
    "traction_motor_temp": (40.0, 130.0),
    "catenary_voltage": (19_000, 29_000),
    "pantograph_current": (0.0, 400.0),
    "transformer_temp": (40.0, 90.0),
    "igbt_temp": (30.0, 85.0),
    "dc_link_voltage": (2_000, 3_200),
    "speed_actual": (0.0, 120.0),
    "brake_pipe_pressure": (4.0, 5.5),
    "wheel_slip_ratio": (0.0, 0.5),
    "crankcase_pressure": (0.0, 50.0),
}

HEALTH_WEIGHTS: dict[str, float] = {
    "brake_pipe_pressure": 0.40,
    "crankcase_pressure": 0.40,
    "oil_pressure": 0.35,
    "igbt_temp": 0.30,
    "catenary_voltage": 0.25,
    "coolant_temp": 0.20,
    "transformer_temp": 0.20,
    "wheel_slip_ratio": 0.20,
    "dc_link_voltage": 0.20,
    "traction_motor_temp": 0.15,
    "diesel_rpm": 0.15,
    "speed_actual": 0.15,
    "pantograph_current": 0.15,
    "fuel_level": 0.10,
    "fuel_rate": 0.10,
    "recuperation_current": 0.05,
}
