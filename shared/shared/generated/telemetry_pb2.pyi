from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TelemetryPoint(_message.Message):
    __slots__ = ("bucket", "locomotive_id", "sensor_type", "avg_value", "min_value", "max_value", "last_value", "unit")
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
    def __init__(self, bucket: _Optional[str] = ..., locomotive_id: _Optional[str] = ..., sensor_type: _Optional[str] = ..., avg_value: _Optional[float] = ..., min_value: _Optional[float] = ..., max_value: _Optional[float] = ..., last_value: _Optional[float] = ..., unit: _Optional[str] = ...) -> None: ...

class TelemetryRawPoint(_message.Message):
    __slots__ = ("time", "locomotive_id", "locomotive_type", "sensor_type", "value", "filtered_value", "unit", "latitude", "longitude")
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
    def __init__(self, time: _Optional[str] = ..., locomotive_id: _Optional[str] = ..., locomotive_type: _Optional[str] = ..., sensor_type: _Optional[str] = ..., value: _Optional[float] = ..., filtered_value: _Optional[float] = ..., unit: _Optional[str] = ..., latitude: _Optional[float] = ..., longitude: _Optional[float] = ...) -> None: ...

class AlertEvent(_message.Message):
    __slots__ = ("id", "locomotive_id", "sensor_type", "severity", "value", "threshold_min", "threshold_max", "message", "recommendation", "timestamp", "acknowledged")
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
    def __init__(self, id: _Optional[str] = ..., locomotive_id: _Optional[str] = ..., sensor_type: _Optional[str] = ..., severity: _Optional[str] = ..., value: _Optional[float] = ..., threshold_min: _Optional[float] = ..., threshold_max: _Optional[float] = ..., message: _Optional[str] = ..., recommendation: _Optional[str] = ..., timestamp: _Optional[str] = ..., acknowledged: bool = ...) -> None: ...

class HealthSnapshot(_message.Message):
    __slots__ = ("locomotive_id", "locomotive_type", "overall_score", "category", "top_factors", "damage_penalty", "calculated_at")
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
    def __init__(self, locomotive_id: _Optional[str] = ..., locomotive_type: _Optional[str] = ..., overall_score: _Optional[float] = ..., category: _Optional[str] = ..., top_factors: _Optional[_Iterable[_Union[HealthFactor, _Mapping]]] = ..., damage_penalty: _Optional[float] = ..., calculated_at: _Optional[str] = ...) -> None: ...

class HealthFactor(_message.Message):
    __slots__ = ("sensor_type", "value", "unit", "penalty", "contribution_pct", "deviation_pct")
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
    def __init__(self, sensor_type: _Optional[str] = ..., value: _Optional[float] = ..., unit: _Optional[str] = ..., penalty: _Optional[float] = ..., contribution_pct: _Optional[float] = ..., deviation_pct: _Optional[float] = ...) -> None: ...

class FleetHealthStats(_message.Message):
    __slots__ = ("bucket", "locomotive_type", "avg_score", "min_score", "max_score", "stddev_score", "locomotive_count", "healthy_count", "warning_count", "critical_count")
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
    def __init__(self, bucket: _Optional[str] = ..., locomotive_type: _Optional[str] = ..., avg_score: _Optional[float] = ..., min_score: _Optional[float] = ..., max_score: _Optional[float] = ..., stddev_score: _Optional[float] = ..., locomotive_count: _Optional[int] = ..., healthy_count: _Optional[int] = ..., warning_count: _Optional[int] = ..., critical_count: _Optional[int] = ...) -> None: ...

class AlertFrequency(_message.Message):
    __slots__ = ("bucket", "sensor_type", "severity", "count")
    BUCKET_FIELD_NUMBER: _ClassVar[int]
    SENSOR_TYPE_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    bucket: str
    sensor_type: str
    severity: str
    count: int
    def __init__(self, bucket: _Optional[str] = ..., sensor_type: _Optional[str] = ..., severity: _Optional[str] = ..., count: _Optional[int] = ...) -> None: ...

class SensorStats(_message.Message):
    __slots__ = ("sensor_type", "unit", "avg", "min", "max", "stddev", "samples")
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
    def __init__(self, sensor_type: _Optional[str] = ..., unit: _Optional[str] = ..., avg: _Optional[float] = ..., min: _Optional[float] = ..., max: _Optional[float] = ..., stddev: _Optional[float] = ..., samples: _Optional[int] = ...) -> None: ...

class WorstLocomotive(_message.Message):
    __slots__ = ("locomotive_id", "locomotive_type", "serial_number", "avg_score", "min_score", "max_score")
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
    def __init__(self, locomotive_id: _Optional[str] = ..., locomotive_type: _Optional[str] = ..., serial_number: _Optional[str] = ..., avg_score: _Optional[float] = ..., min_score: _Optional[float] = ..., max_score: _Optional[float] = ...) -> None: ...

class TelemetryBucketedRequest(_message.Message):
    __slots__ = ("locomotive_id", "sensor_type", "start", "end", "offset", "limit", "bucket_interval")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    SENSOR_TYPE_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    BUCKET_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    sensor_type: str
    start: str
    end: str
    offset: int
    limit: int
    bucket_interval: str
    def __init__(self, locomotive_id: _Optional[str] = ..., sensor_type: _Optional[str] = ..., start: _Optional[str] = ..., end: _Optional[str] = ..., offset: _Optional[int] = ..., limit: _Optional[int] = ..., bucket_interval: _Optional[str] = ...) -> None: ...

class TelemetryBucketedResponse(_message.Message):
    __slots__ = ("points", "data_source", "total_points")
    POINTS_FIELD_NUMBER: _ClassVar[int]
    DATA_SOURCE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_POINTS_FIELD_NUMBER: _ClassVar[int]
    points: _containers.RepeatedCompositeFieldContainer[TelemetryPoint]
    data_source: str
    total_points: int
    def __init__(self, points: _Optional[_Iterable[_Union[TelemetryPoint, _Mapping]]] = ..., data_source: _Optional[str] = ..., total_points: _Optional[int] = ...) -> None: ...

class TelemetryRawRequest(_message.Message):
    __slots__ = ("locomotive_id", "sensor_type", "start", "end", "offset", "limit")
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
    def __init__(self, locomotive_id: _Optional[str] = ..., sensor_type: _Optional[str] = ..., start: _Optional[str] = ..., end: _Optional[str] = ..., offset: _Optional[int] = ..., limit: _Optional[int] = ...) -> None: ...

class TelemetryRawResponse(_message.Message):
    __slots__ = ("points",)
    POINTS_FIELD_NUMBER: _ClassVar[int]
    points: _containers.RepeatedCompositeFieldContainer[TelemetryRawPoint]
    def __init__(self, points: _Optional[_Iterable[_Union[TelemetryRawPoint, _Mapping]]] = ...) -> None: ...

class TelemetrySnapshotRequest(_message.Message):
    __slots__ = ("locomotive_id", "at")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    AT_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    at: str
    def __init__(self, locomotive_id: _Optional[str] = ..., at: _Optional[str] = ...) -> None: ...

class TelemetrySnapshotResponse(_message.Message):
    __slots__ = ("points",)
    POINTS_FIELD_NUMBER: _ClassVar[int]
    points: _containers.RepeatedCompositeFieldContainer[TelemetryRawPoint]
    def __init__(self, points: _Optional[_Iterable[_Union[TelemetryRawPoint, _Mapping]]] = ...) -> None: ...

class AlertsListRequest(_message.Message):
    __slots__ = ("locomotive_id", "severity", "filter_acknowledged", "acknowledged", "start", "end", "offset", "limit")
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
    def __init__(self, locomotive_id: _Optional[str] = ..., severity: _Optional[str] = ..., filter_acknowledged: bool = ..., acknowledged: bool = ..., start: _Optional[str] = ..., end: _Optional[str] = ..., offset: _Optional[int] = ..., limit: _Optional[int] = ...) -> None: ...

class AlertsListResponse(_message.Message):
    __slots__ = ("alerts", "total")
    ALERTS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    alerts: _containers.RepeatedCompositeFieldContainer[AlertEvent]
    total: int
    def __init__(self, alerts: _Optional[_Iterable[_Union[AlertEvent, _Mapping]]] = ..., total: _Optional[int] = ...) -> None: ...

class AlertGetRequest(_message.Message):
    __slots__ = ("alert_id",)
    ALERT_ID_FIELD_NUMBER: _ClassVar[int]
    alert_id: str
    def __init__(self, alert_id: _Optional[str] = ...) -> None: ...

class AlertAcknowledgeRequest(_message.Message):
    __slots__ = ("alert_id",)
    ALERT_ID_FIELD_NUMBER: _ClassVar[int]
    alert_id: str
    def __init__(self, alert_id: _Optional[str] = ...) -> None: ...

class HealthCurrentRequest(_message.Message):
    __slots__ = ("locomotive_id",)
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    def __init__(self, locomotive_id: _Optional[str] = ...) -> None: ...

class HealthAtRequest(_message.Message):
    __slots__ = ("locomotive_id", "at")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    AT_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    at: str
    def __init__(self, locomotive_id: _Optional[str] = ..., at: _Optional[str] = ...) -> None: ...

class FleetHealthRequest(_message.Message):
    __slots__ = ("start", "end", "locomotive_type")
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    LOCOMOTIVE_TYPE_FIELD_NUMBER: _ClassVar[int]
    start: str
    end: str
    locomotive_type: str
    def __init__(self, start: _Optional[str] = ..., end: _Optional[str] = ..., locomotive_type: _Optional[str] = ...) -> None: ...

class FleetHealthResponse(_message.Message):
    __slots__ = ("stats",)
    STATS_FIELD_NUMBER: _ClassVar[int]
    stats: _containers.RepeatedCompositeFieldContainer[FleetHealthStats]
    def __init__(self, stats: _Optional[_Iterable[_Union[FleetHealthStats, _Mapping]]] = ...) -> None: ...

class AlertFrequencyRequest(_message.Message):
    __slots__ = ("start", "end", "sensor_type", "severity")
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    SENSOR_TYPE_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    start: str
    end: str
    sensor_type: str
    severity: str
    def __init__(self, start: _Optional[str] = ..., end: _Optional[str] = ..., sensor_type: _Optional[str] = ..., severity: _Optional[str] = ...) -> None: ...

class AlertFrequencyResponse(_message.Message):
    __slots__ = ("frequencies",)
    FREQUENCIES_FIELD_NUMBER: _ClassVar[int]
    frequencies: _containers.RepeatedCompositeFieldContainer[AlertFrequency]
    def __init__(self, frequencies: _Optional[_Iterable[_Union[AlertFrequency, _Mapping]]] = ...) -> None: ...

class SensorStatsRequest(_message.Message):
    __slots__ = ("locomotive_id", "start", "end")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    start: str
    end: str
    def __init__(self, locomotive_id: _Optional[str] = ..., start: _Optional[str] = ..., end: _Optional[str] = ...) -> None: ...

class SensorStatsResponse(_message.Message):
    __slots__ = ("stats", "locomotive_type")
    STATS_FIELD_NUMBER: _ClassVar[int]
    LOCOMOTIVE_TYPE_FIELD_NUMBER: _ClassVar[int]
    stats: _containers.RepeatedCompositeFieldContainer[SensorStats]
    locomotive_type: str
    def __init__(self, stats: _Optional[_Iterable[_Union[SensorStats, _Mapping]]] = ..., locomotive_type: _Optional[str] = ...) -> None: ...

class HealthTrendRequest(_message.Message):
    __slots__ = ("locomotive_id", "start", "end")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    start: str
    end: str
    def __init__(self, locomotive_id: _Optional[str] = ..., start: _Optional[str] = ..., end: _Optional[str] = ...) -> None: ...

class HealthTrendPoint(_message.Message):
    __slots__ = ("time", "avg_score", "min_score", "max_score")
    TIME_FIELD_NUMBER: _ClassVar[int]
    AVG_SCORE_FIELD_NUMBER: _ClassVar[int]
    MIN_SCORE_FIELD_NUMBER: _ClassVar[int]
    MAX_SCORE_FIELD_NUMBER: _ClassVar[int]
    time: str
    avg_score: float
    min_score: float
    max_score: float
    def __init__(self, time: _Optional[str] = ..., avg_score: _Optional[float] = ..., min_score: _Optional[float] = ..., max_score: _Optional[float] = ...) -> None: ...

class HealthTrendResponse(_message.Message):
    __slots__ = ("points",)
    POINTS_FIELD_NUMBER: _ClassVar[int]
    points: _containers.RepeatedCompositeFieldContainer[HealthTrendPoint]
    def __init__(self, points: _Optional[_Iterable[_Union[HealthTrendPoint, _Mapping]]] = ...) -> None: ...

class LatestHealthRequest(_message.Message):
    __slots__ = ("locomotive_id", "start", "end")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    start: str
    end: str
    def __init__(self, locomotive_id: _Optional[str] = ..., start: _Optional[str] = ..., end: _Optional[str] = ...) -> None: ...

class LatestHealthResponse(_message.Message):
    __slots__ = ("avg_score", "min_score", "max_score", "category", "damage_penalty", "top_factors")
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
    def __init__(self, avg_score: _Optional[float] = ..., min_score: _Optional[float] = ..., max_score: _Optional[float] = ..., category: _Optional[str] = ..., damage_penalty: _Optional[float] = ..., top_factors: _Optional[_Iterable[_Union[HealthFactor, _Mapping]]] = ...) -> None: ...

class WorstLocomotivesRequest(_message.Message):
    __slots__ = ("start", "end", "limit")
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    start: str
    end: str
    limit: int
    def __init__(self, start: _Optional[str] = ..., end: _Optional[str] = ..., limit: _Optional[int] = ...) -> None: ...

class WorstLocomotivesResponse(_message.Message):
    __slots__ = ("locomotives",)
    LOCOMOTIVES_FIELD_NUMBER: _ClassVar[int]
    locomotives: _containers.RepeatedCompositeFieldContainer[WorstLocomotive]
    def __init__(self, locomotives: _Optional[_Iterable[_Union[WorstLocomotive, _Mapping]]] = ...) -> None: ...

class FleetAlertSummaryRequest(_message.Message):
    __slots__ = ("start", "end")
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    start: str
    end: str
    def __init__(self, start: _Optional[str] = ..., end: _Optional[str] = ...) -> None: ...

class FleetAlertSummaryResponse(_message.Message):
    __slots__ = ("total", "by_severity")
    class BySeverityEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    BY_SEVERITY_FIELD_NUMBER: _ClassVar[int]
    total: int
    by_severity: _containers.ScalarMap[str, int]
    def __init__(self, total: _Optional[int] = ..., by_severity: _Optional[_Mapping[str, int]] = ...) -> None: ...

class ReportAlertsRequest(_message.Message):
    __slots__ = ("locomotive_id", "start", "end")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    start: str
    end: str
    def __init__(self, locomotive_id: _Optional[str] = ..., start: _Optional[str] = ..., end: _Optional[str] = ...) -> None: ...

class ReportAlertsResponse(_message.Message):
    __slots__ = ("alerts",)
    ALERTS_FIELD_NUMBER: _ClassVar[int]
    alerts: _containers.RepeatedCompositeFieldContainer[AlertEvent]
    def __init__(self, alerts: _Optional[_Iterable[_Union[AlertEvent, _Mapping]]] = ...) -> None: ...

class RawForAnomaliesRequest(_message.Message):
    __slots__ = ("locomotive_id", "start", "end")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    start: str
    end: str
    def __init__(self, locomotive_id: _Optional[str] = ..., start: _Optional[str] = ..., end: _Optional[str] = ...) -> None: ...

class AnomalyDataPoint(_message.Message):
    __slots__ = ("sensor_type", "filtered_value", "time")
    SENSOR_TYPE_FIELD_NUMBER: _ClassVar[int]
    FILTERED_VALUE_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    sensor_type: str
    filtered_value: float
    time: str
    def __init__(self, sensor_type: _Optional[str] = ..., filtered_value: _Optional[float] = ..., time: _Optional[str] = ...) -> None: ...

class RawForAnomaliesResponse(_message.Message):
    __slots__ = ("points",)
    POINTS_FIELD_NUMBER: _ClassVar[int]
    points: _containers.RepeatedCompositeFieldContainer[AnomalyDataPoint]
    def __init__(self, points: _Optional[_Iterable[_Union[AnomalyDataPoint, _Mapping]]] = ...) -> None: ...

class FleetLatestSnapshotsResponse(_message.Message):
    __slots__ = ("entries",)
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    entries: _containers.RepeatedCompositeFieldContainer[FleetSnapshotEntry]
    def __init__(self, entries: _Optional[_Iterable[_Union[FleetSnapshotEntry, _Mapping]]] = ...) -> None: ...

class FleetSnapshotEntry(_message.Message):
    __slots__ = ("locomotive_id", "locomotive_type", "score", "category")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    LOCOMOTIVE_TYPE_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    locomotive_type: str
    score: float
    category: str
    def __init__(self, locomotive_id: _Optional[str] = ..., locomotive_type: _Optional[str] = ..., score: _Optional[float] = ..., category: _Optional[str] = ...) -> None: ...

class UtilizationRequest(_message.Message):
    __slots__ = ("locomotive_id", "hours")
    LOCOMOTIVE_ID_FIELD_NUMBER: _ClassVar[int]
    HOURS_FIELD_NUMBER: _ClassVar[int]
    locomotive_id: str
    hours: int
    def __init__(self, locomotive_id: _Optional[str] = ..., hours: _Optional[int] = ...) -> None: ...

class UtilizationResponse(_message.Message):
    __slots__ = ("total_readings", "active_readings", "avg_speed", "max_speed")
    TOTAL_READINGS_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_READINGS_FIELD_NUMBER: _ClassVar[int]
    AVG_SPEED_FIELD_NUMBER: _ClassVar[int]
    MAX_SPEED_FIELD_NUMBER: _ClassVar[int]
    total_readings: int
    active_readings: int
    avg_speed: float
    max_speed: float
    def __init__(self, total_readings: _Optional[int] = ..., active_readings: _Optional[int] = ..., avg_speed: _Optional[float] = ..., max_speed: _Optional[float] = ...) -> None: ...

class Empty(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
