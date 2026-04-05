from collections.abc import Iterable as _Iterable
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf.internal import containers as _containers

DESCRIPTOR: _descriptor.FileDescriptor

class TelemetryPoint(_message.Message):
    __slots__ = ("avg_value", "bucket", "last_value", "locomotive_id", "max_value", "min_value", "sensor_type", "unit")
    BUCKET_FIELD_NUMBER: _ClassVar[int]
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    SENSOR_TYPE_FIELD_NUMBER: _ClassVar[int]
    AVG_VALUE_FIELD_NUMBER: _ClassVar[int]
    MIN_VALUE_FIELD_NUMBER: _ClassVar[int]
    MAX_VALUE_FIELD_NUMBER: _ClassVar[int]
    LAST_VALUE_FIELD_NUMBER: _ClassVar[int]
    UNIT_FIELD_NUMBER: _ClassVar[int]
    bucket: str
    locomotive_id: str
    sensor_type: str
    avg_value: float
    min_value: float
    max_value: float
    last_value: float
    unit: str
    def __init__(
        self,
        bucket: str | None = ...,
        locomotive_id: str | None = ...,
        sensor_type: str | None = ...,
        avg_value: float | None = ...,
        min_value: float | None = ...,
        max_value: float | None = ...,
        last_value: float | None = ...,
        unit: str | None = ...,
    ) -> None: ...

class TelemetryRawPoint(_message.Message):
    __slots__ = (
        "filtered_value",
        "latitude",
        "locomotive_id",
        "locomotive_type",
        "longitude",
        "sensor_type",
        "time",
        "unit",
        "value",
    )
    TIME_FIELD_NUMBER: _ClassVar[int]
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    LOCOMOTIVE_TYPE_FIELD_NUMBER: _ClassVar[int]
    SENSOR_TYPE_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    FILTERED_VALUE_FIELD_NUMBER: _ClassVar[int]
    UNIT_FIELD_NUMBER: _ClassVar[int]
    LATITUDE_FIELD_NUMBER: _ClassVar[int]
    LONGITUDE_FIELD_NUMBER: _ClassVar[int]
    time: str
    locomotive_id: str
    locomotive_type: str
    sensor_type: str
    value: float
    filtered_value: float
    unit: str
    latitude: float
    longitude: float
    def __init__(
        self,
        time: str | None = ...,
        locomotive_id: str | None = ...,
        locomotive_type: str | None = ...,
        sensor_type: str | None = ...,
        value: float | None = ...,
        filtered_value: float | None = ...,
        unit: str | None = ...,
        latitude: float | None = ...,
        longitude: float | None = ...,
    ) -> None: ...

class AlertEvent(_message.Message):
    __slots__ = (
        "acknowledged",
        "id",
        "locomotive_id",
        "message",
        "recommendation",
        "sensor_type",
        "severity",
        "threshold_max",
        "threshold_min",
        "timestamp",
        "value",
    )
    ID_FIELD_NUMBER: _ClassVar[int]
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    SENSOR_TYPE_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    THRESHOLD_MIN_FIELD_NUMBER: _ClassVar[int]
    THRESHOLD_MAX_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    RECOMMENDATION_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    ACKNOWLEDGED_FIELD_NUMBER: _ClassVar[int]
    id: str
    locomotive_id: str
    sensor_type: str
    severity: str
    value: float
    threshold_min: float
    threshold_max: float
    message: str
    recommendation: str
    timestamp: str
    acknowledged: bool
    def __init__(
        self,
        id: str | None = ...,
        locomotive_id: str | None = ...,
        sensor_type: str | None = ...,
        severity: str | None = ...,
        value: float | None = ...,
        threshold_min: float | None = ...,
        threshold_max: float | None = ...,
        message: str | None = ...,
        recommendation: str | None = ...,
        timestamp: str | None = ...,
        acknowledged: bool = ...,
    ) -> None: ...

class HealthSnapshot(_message.Message):
    __slots__ = (
        "calculated_at",
        "category",
        "damage_penalty",
        "locomotive_id",
        "locomotive_type",
        "overall_score",
        "top_factors",
    )
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    LOCOMOTIVE_TYPE_FIELD_NUMBER: _ClassVar[int]
    OVERALL_SCORE_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    TOP_FACTORS_FIELD_NUMBER: _ClassVar[int]
    DAMAGE_PENALTY_FIELD_NUMBER: _ClassVar[int]
    CALCULATED_AT_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    locomotive_type: str
    overall_score: float
    category: str
    top_factors: _containers.RepeatedCompositeFieldContainer[HealthFactor]
    damage_penalty: float
    calculated_at: str
    def __init__(
        self,
        locomotive_id: str | None = ...,
        locomotive_type: str | None = ...,
        overall_score: float | None = ...,
        category: str | None = ...,
        top_factors: _Iterable[HealthFactor | _Mapping] | None = ...,
        damage_penalty: float | None = ...,
        calculated_at: str | None = ...,
    ) -> None: ...

class HealthFactor(_message.Message):
    __slots__ = ("contribution_pct", "deviation_pct", "penalty", "sensor_type", "unit", "value")
    SENSOR_TYPE_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    UNIT_FIELD_NUMBER: _ClassVar[int]
    PENALTY_FIELD_NUMBER: _ClassVar[int]
    CONTRIBUTION_PCT_FIELD_NUMBER: _ClassVar[int]
    DEVIATION_PCT_FIELD_NUMBER: _ClassVar[int]
    sensor_type: str
    value: float
    unit: str
    penalty: float
    contribution_pct: float
    deviation_pct: float
    def __init__(
        self,
        sensor_type: str | None = ...,
        value: float | None = ...,
        unit: str | None = ...,
        penalty: float | None = ...,
        contribution_pct: float | None = ...,
        deviation_pct: float | None = ...,
    ) -> None: ...

class FleetHealthStats(_message.Message):
    __slots__ = (
        "avg_score",
        "bucket",
        "critical_count",
        "healthy_count",
        "locomotive_count",
        "locomotive_type",
        "max_score",
        "min_score",
        "stddev_score",
        "warning_count",
    )
    BUCKET_FIELD_NUMBER: _ClassVar[int]
    LOCOMOTIVE_TYPE_FIELD_NUMBER: _ClassVar[int]
    AVG_SCORE_FIELD_NUMBER: _ClassVar[int]
    MIN_SCORE_FIELD_NUMBER: _ClassVar[int]
    MAX_SCORE_FIELD_NUMBER: _ClassVar[int]
    STDDEV_SCORE_FIELD_NUMBER: _ClassVar[int]
    LOCOMOTIVE_COUNT_FIELD_NUMBER: _ClassVar[int]
    HEALTHY_COUNT_FIELD_NUMBER: _ClassVar[int]
    WARNING_COUNT_FIELD_NUMBER: _ClassVar[int]
    CRITICAL_COUNT_FIELD_NUMBER: _ClassVar[int]
    bucket: str
    locomotive_type: str
    avg_score: float
    min_score: float
    max_score: float
    stddev_score: float
    locomotive_count: int
    healthy_count: int
    warning_count: int
    critical_count: int
    def __init__(
        self,
        bucket: str | None = ...,
        locomotive_type: str | None = ...,
        avg_score: float | None = ...,
        min_score: float | None = ...,
        max_score: float | None = ...,
        stddev_score: float | None = ...,
        locomotive_count: int | None = ...,
        healthy_count: int | None = ...,
        warning_count: int | None = ...,
        critical_count: int | None = ...,
    ) -> None: ...

class AlertFrequency(_message.Message):
    __slots__ = ("bucket", "count", "sensor_type", "severity")
    BUCKET_FIELD_NUMBER: _ClassVar[int]
    SENSOR_TYPE_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    bucket: str
    sensor_type: str
    severity: str
    count: int
    def __init__(
        self,
        bucket: str | None = ...,
        sensor_type: str | None = ...,
        severity: str | None = ...,
        count: int | None = ...,
    ) -> None: ...

class SensorStats(_message.Message):
    __slots__ = ("avg", "max", "min", "samples", "sensor_type", "stddev", "unit")
    SENSOR_TYPE_FIELD_NUMBER: _ClassVar[int]
    UNIT_FIELD_NUMBER: _ClassVar[int]
    AVG_FIELD_NUMBER: _ClassVar[int]
    MIN_FIELD_NUMBER: _ClassVar[int]
    MAX_FIELD_NUMBER: _ClassVar[int]
    STDDEV_FIELD_NUMBER: _ClassVar[int]
    SAMPLES_FIELD_NUMBER: _ClassVar[int]
    sensor_type: str
    unit: str
    avg: float
    min: float
    max: float
    stddev: float
    samples: int
    def __init__(
        self,
        sensor_type: str | None = ...,
        unit: str | None = ...,
        avg: float | None = ...,
        min: float | None = ...,
        max: float | None = ...,
        stddev: float | None = ...,
        samples: int | None = ...,
    ) -> None: ...

class WorstLocomotive(_message.Message):
    __slots__ = ("avg_score", "locomotive_id", "locomotive_type", "max_score", "min_score", "serial_number")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    LOCOMOTIVE_TYPE_FIELD_NUMBER: _ClassVar[int]
    SERIAL_NUMBER_FIELD_NUMBER: _ClassVar[int]
    AVG_SCORE_FIELD_NUMBER: _ClassVar[int]
    MIN_SCORE_FIELD_NUMBER: _ClassVar[int]
    MAX_SCORE_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    locomotive_type: str
    serial_number: str
    avg_score: float
    min_score: float
    max_score: float
    def __init__(
        self,
        locomotive_id: str | None = ...,
        locomotive_type: str | None = ...,
        serial_number: str | None = ...,
        avg_score: float | None = ...,
        min_score: float | None = ...,
        max_score: float | None = ...,
    ) -> None: ...

class TelemetryBucketedRequest(_message.Message):
    __slots__ = ("end", "limit", "locomotive_id", "offset", "sensor_type", "start")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    SENSOR_TYPE_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    sensor_type: str
    start: str
    end: str
    offset: int
    limit: int
    def __init__(
        self,
        locomotive_id: str | None = ...,
        sensor_type: str | None = ...,
        start: str | None = ...,
        end: str | None = ...,
        offset: int | None = ...,
        limit: int | None = ...,
    ) -> None: ...

class TelemetryBucketedResponse(_message.Message):
    __slots__ = ("data_source", "points", "total_points")
    POINTS_FIELD_NUMBER: _ClassVar[int]
    DATA_SOURCE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_POINTS_FIELD_NUMBER: _ClassVar[int]
    points: _containers.RepeatedCompositeFieldContainer[TelemetryPoint]
    data_source: str
    total_points: int
    def __init__(
        self,
        points: _Iterable[TelemetryPoint | _Mapping] | None = ...,
        data_source: str | None = ...,
        total_points: int | None = ...,
    ) -> None: ...

class TelemetryRawRequest(_message.Message):
    __slots__ = ("end", "limit", "locomotive_id", "offset", "sensor_type", "start")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    SENSOR_TYPE_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    sensor_type: str
    start: str
    end: str
    offset: int
    limit: int
    def __init__(
        self,
        locomotive_id: str | None = ...,
        sensor_type: str | None = ...,
        start: str | None = ...,
        end: str | None = ...,
        offset: int | None = ...,
        limit: int | None = ...,
    ) -> None: ...

class TelemetryRawResponse(_message.Message):
    __slots__ = ("points",)
    POINTS_FIELD_NUMBER: _ClassVar[int]
    points: _containers.RepeatedCompositeFieldContainer[TelemetryRawPoint]
    def __init__(self, points: _Iterable[TelemetryRawPoint | _Mapping] | None = ...) -> None: ...

class TelemetrySnapshotRequest(_message.Message):
    __slots__ = ("at", "locomotive_id")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    AT_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    at: str
    def __init__(self, locomotive_id: str | None = ..., at: str | None = ...) -> None: ...

class TelemetrySnapshotResponse(_message.Message):
    __slots__ = ("points",)
    POINTS_FIELD_NUMBER: _ClassVar[int]
    points: _containers.RepeatedCompositeFieldContainer[TelemetryRawPoint]
    def __init__(self, points: _Iterable[TelemetryRawPoint | _Mapping] | None = ...) -> None: ...

class AlertsListRequest(_message.Message):
    __slots__ = ("acknowledged", "end", "filter_acknowledged", "limit", "locomotive_id", "offset", "severity", "start")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    FILTER_ACKNOWLEDGED_FIELD_NUMBER: _ClassVar[int]
    ACKNOWLEDGED_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    severity: str
    filter_acknowledged: bool
    acknowledged: bool
    start: str
    end: str
    offset: int
    limit: int
    def __init__(
        self,
        locomotive_id: str | None = ...,
        severity: str | None = ...,
        filter_acknowledged: bool = ...,
        acknowledged: bool = ...,
        start: str | None = ...,
        end: str | None = ...,
        offset: int | None = ...,
        limit: int | None = ...,
    ) -> None: ...

class AlertsListResponse(_message.Message):
    __slots__ = ("alerts", "total")
    ALERTS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    alerts: _containers.RepeatedCompositeFieldContainer[AlertEvent]
    total: int
    def __init__(self, alerts: _Iterable[AlertEvent | _Mapping] | None = ..., total: int | None = ...) -> None: ...

class AlertGetRequest(_message.Message):
    __slots__ = ("alert_id",)
    ALERT_ID_FIELD_NUMBER: _ClassVar[int]
    alert_id: str
    def __init__(self, alert_id: str | None = ...) -> None: ...

class AlertAcknowledgeRequest(_message.Message):
    __slots__ = ("alert_id",)
    ALERT_ID_FIELD_NUMBER: _ClassVar[int]
    alert_id: str
    def __init__(self, alert_id: str | None = ...) -> None: ...

class HealthCurrentRequest(_message.Message):
    __slots__ = ("locomotive_id",)
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    def __init__(self, locomotive_id: str | None = ...) -> None: ...

class HealthAtRequest(_message.Message):
    __slots__ = ("at", "locomotive_id")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    AT_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    at: str
    def __init__(self, locomotive_id: str | None = ..., at: str | None = ...) -> None: ...

class FleetHealthRequest(_message.Message):
    __slots__ = ("end", "locomotive_type", "start")
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    LOCOMOTIVE_TYPE_FIELD_NUMBER: _ClassVar[int]
    start: str
    end: str
    locomotive_type: str
    def __init__(self, start: str | None = ..., end: str | None = ..., locomotive_type: str | None = ...) -> None: ...

class FleetHealthResponse(_message.Message):
    __slots__ = ("stats",)
    STATS_FIELD_NUMBER: _ClassVar[int]
    stats: _containers.RepeatedCompositeFieldContainer[FleetHealthStats]
    def __init__(self, stats: _Iterable[FleetHealthStats | _Mapping] | None = ...) -> None: ...

class AlertFrequencyRequest(_message.Message):
    __slots__ = ("end", "sensor_type", "severity", "start")
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    SENSOR_TYPE_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    start: str
    end: str
    sensor_type: str
    severity: str
    def __init__(
        self,
        start: str | None = ...,
        end: str | None = ...,
        sensor_type: str | None = ...,
        severity: str | None = ...,
    ) -> None: ...

class AlertFrequencyResponse(_message.Message):
    __slots__ = ("frequencies",)
    FREQUENCIES_FIELD_NUMBER: _ClassVar[int]
    frequencies: _containers.RepeatedCompositeFieldContainer[AlertFrequency]
    def __init__(self, frequencies: _Iterable[AlertFrequency | _Mapping] | None = ...) -> None: ...

class SensorStatsRequest(_message.Message):
    __slots__ = ("end", "locomotive_id", "start")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    start: str
    end: str
    def __init__(self, locomotive_id: str | None = ..., start: str | None = ..., end: str | None = ...) -> None: ...

class SensorStatsResponse(_message.Message):
    __slots__ = ("locomotive_type", "stats")
    STATS_FIELD_NUMBER: _ClassVar[int]
    LOCOMOTIVE_TYPE_FIELD_NUMBER: _ClassVar[int]
    stats: _containers.RepeatedCompositeFieldContainer[SensorStats]
    locomotive_type: str
    def __init__(
        self, stats: _Iterable[SensorStats | _Mapping] | None = ..., locomotive_type: str | None = ...
    ) -> None: ...

class HealthTrendRequest(_message.Message):
    __slots__ = ("end", "locomotive_id", "start")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    start: str
    end: str
    def __init__(self, locomotive_id: str | None = ..., start: str | None = ..., end: str | None = ...) -> None: ...

class HealthTrendPoint(_message.Message):
    __slots__ = ("avg_score", "max_score", "min_score", "time")
    TIME_FIELD_NUMBER: _ClassVar[int]
    AVG_SCORE_FIELD_NUMBER: _ClassVar[int]
    MIN_SCORE_FIELD_NUMBER: _ClassVar[int]
    MAX_SCORE_FIELD_NUMBER: _ClassVar[int]
    time: str
    avg_score: float
    min_score: float
    max_score: float
    def __init__(
        self,
        time: str | None = ...,
        avg_score: float | None = ...,
        min_score: float | None = ...,
        max_score: float | None = ...,
    ) -> None: ...

class HealthTrendResponse(_message.Message):
    __slots__ = ("points",)
    POINTS_FIELD_NUMBER: _ClassVar[int]
    points: _containers.RepeatedCompositeFieldContainer[HealthTrendPoint]
    def __init__(self, points: _Iterable[HealthTrendPoint | _Mapping] | None = ...) -> None: ...

class LatestHealthRequest(_message.Message):
    __slots__ = ("end", "locomotive_id", "start")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    start: str
    end: str
    def __init__(self, locomotive_id: str | None = ..., start: str | None = ..., end: str | None = ...) -> None: ...

class LatestHealthResponse(_message.Message):
    __slots__ = ("avg_score", "category", "damage_penalty", "max_score", "min_score", "top_factors")
    AVG_SCORE_FIELD_NUMBER: _ClassVar[int]
    MIN_SCORE_FIELD_NUMBER: _ClassVar[int]
    MAX_SCORE_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    DAMAGE_PENALTY_FIELD_NUMBER: _ClassVar[int]
    TOP_FACTORS_FIELD_NUMBER: _ClassVar[int]
    avg_score: float
    min_score: float
    max_score: float
    category: str
    damage_penalty: float
    top_factors: _containers.RepeatedCompositeFieldContainer[HealthFactor]
    def __init__(
        self,
        avg_score: float | None = ...,
        min_score: float | None = ...,
        max_score: float | None = ...,
        category: str | None = ...,
        damage_penalty: float | None = ...,
        top_factors: _Iterable[HealthFactor | _Mapping] | None = ...,
    ) -> None: ...

class WorstLocomotivesRequest(_message.Message):
    __slots__ = ("end", "limit", "start")
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    start: str
    end: str
    limit: int
    def __init__(self, start: str | None = ..., end: str | None = ..., limit: int | None = ...) -> None: ...

class WorstLocomotivesResponse(_message.Message):
    __slots__ = ("locomotives",)
    LOCOMOTIVES_FIELD_NUMBER: _ClassVar[int]
    locomotives: _containers.RepeatedCompositeFieldContainer[WorstLocomotive]
    def __init__(self, locomotives: _Iterable[WorstLocomotive | _Mapping] | None = ...) -> None: ...

class FleetAlertSummaryRequest(_message.Message):
    __slots__ = ("end", "start")
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    start: str
    end: str
    def __init__(self, start: str | None = ..., end: str | None = ...) -> None: ...

class FleetAlertSummaryResponse(_message.Message):
    __slots__ = ("by_severity", "total")
    class BySeverityEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: str | None = ..., value: int | None = ...) -> None: ...

    TOTAL_FIELD_NUMBER: _ClassVar[int]
    BY_SEVERITY_FIELD_NUMBER: _ClassVar[int]
    total: int
    by_severity: _containers.ScalarMap[str, int]
    def __init__(self, total: int | None = ..., by_severity: _Mapping[str, int] | None = ...) -> None: ...

class ReportAlertsRequest(_message.Message):
    __slots__ = ("end", "locomotive_id", "start")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    start: str
    end: str
    def __init__(self, locomotive_id: str | None = ..., start: str | None = ..., end: str | None = ...) -> None: ...

class ReportAlertsResponse(_message.Message):
    __slots__ = ("alerts",)
    ALERTS_FIELD_NUMBER: _ClassVar[int]
    alerts: _containers.RepeatedCompositeFieldContainer[AlertEvent]
    def __init__(self, alerts: _Iterable[AlertEvent | _Mapping] | None = ...) -> None: ...

class RawForAnomaliesRequest(_message.Message):
    __slots__ = ("end", "locomotive_id", "start")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    start: str
    end: str
    def __init__(self, locomotive_id: str | None = ..., start: str | None = ..., end: str | None = ...) -> None: ...

class AnomalyDataPoint(_message.Message):
    __slots__ = ("filtered_value", "sensor_type", "time")
    SENSOR_TYPE_FIELD_NUMBER: _ClassVar[int]
    FILTERED_VALUE_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    sensor_type: str
    filtered_value: float
    time: str
    def __init__(
        self, sensor_type: str | None = ..., filtered_value: float | None = ..., time: str | None = ...
    ) -> None: ...

class RawForAnomaliesResponse(_message.Message):
    __slots__ = ("points",)
    POINTS_FIELD_NUMBER: _ClassVar[int]
    points: _containers.RepeatedCompositeFieldContainer[AnomalyDataPoint]
    def __init__(self, points: _Iterable[AnomalyDataPoint | _Mapping] | None = ...) -> None: ...

class FleetLatestSnapshotsResponse(_message.Message):
    __slots__ = ("entries",)
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    entries: _containers.RepeatedCompositeFieldContainer[FleetSnapshotEntry]
    def __init__(self, entries: _Iterable[FleetSnapshotEntry | _Mapping] | None = ...) -> None: ...

class FleetSnapshotEntry(_message.Message):
    __slots__ = ("category", "locomotive_id", "locomotive_type", "score")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    LOCOMOTIVE_TYPE_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    locomotive_type: str
    score: float
    category: str
    def __init__(
        self,
        locomotive_id: str | None = ...,
        locomotive_type: str | None = ...,
        score: float | None = ...,
        category: str | None = ...,
    ) -> None: ...

class UtilizationRequest(_message.Message):
    __slots__ = ("hours", "locomotive_id")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    HOURS_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    hours: int
    def __init__(self, locomotive_id: str | None = ..., hours: int | None = ...) -> None: ...

class UtilizationResponse(_message.Message):
    __slots__ = ("active_readings", "avg_speed", "max_speed", "total_readings")
    TOTAL_READINGS_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_READINGS_FIELD_NUMBER: _ClassVar[int]
    AVG_SPEED_FIELD_NUMBER: _ClassVar[int]
    MAX_SPEED_FIELD_NUMBER: _ClassVar[int]
    total_readings: int
    active_readings: int
    avg_speed: float
    max_speed: float
    def __init__(
        self,
        total_readings: int | None = ...,
        active_readings: int | None = ...,
        avg_speed: float | None = ...,
        max_speed: float | None = ...,
    ) -> None: ...

class Empty(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
