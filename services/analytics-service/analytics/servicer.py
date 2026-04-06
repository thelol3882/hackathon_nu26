"""gRPC service implementation — translates requests into repository calls."""

from __future__ import annotations

from datetime import UTC, datetime

import grpc

from analytics.background.health_cache import get_cached_health
from analytics.core.database import get_session_factory
from analytics.core.redis_client import get_redis_raw
from analytics.repositories import alert_repository, health_repository, telemetry_repository
from shared.generated import telemetry_pb2, telemetry_pb2_grpc
from shared.observability import get_logger
from shared.wire import decode as wire_decode

logger = get_logger(__name__)


def _parse_dt(s: str) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s)


class AnalyticsServicer(telemetry_pb2_grpc.AnalyticsServiceServicer):
    """Implements all RPC methods defined in telemetry.proto."""

    async def GetTelemetryBucketed(self, request, context):
        factory = get_session_factory()
        async with factory() as session:
            rows, data_source = await telemetry_repository.query_bucketed(
                session,
                locomotive_id=request.locomotive_id or None,
                sensor_type=request.sensor_type or None,
                start=_parse_dt(request.start),
                end=_parse_dt(request.end),
                offset=request.offset,
                limit=request.limit or 500,
                bucket_interval=request.bucket_interval or None,
                max_points=request.max_points or 0,
            )
        points = [
            telemetry_pb2.TelemetryPoint(
                bucket=str(r["bucket"]),
                locomotive_id=str(r["locomotive_id"]),
                sensor_type=r["sensor_type"],
                avg_value=float(r["avg_value"]) if r["avg_value"] is not None else 0.0,
                min_value=float(r["min_value"]) if r["min_value"] is not None else 0.0,
                max_value=float(r["max_value"]) if r["max_value"] is not None else 0.0,
                last_value=float(r["last_value"]) if r["last_value"] is not None else 0.0,
                unit=r.get("unit", "") or "",
                is_gap=r["avg_value"] is None,
            )
            for r in rows
        ]
        return telemetry_pb2.TelemetryBucketedResponse(
            points=points,
            data_source=data_source,
            total_points=len(points),
        )

    async def GetTelemetryRaw(self, request, context):
        factory = get_session_factory()
        async with factory() as session:
            rows = await telemetry_repository.query_raw(
                session,
                locomotive_id=request.locomotive_id or None,
                sensor_type=request.sensor_type or None,
                start=_parse_dt(request.start),
                end=_parse_dt(request.end),
                offset=request.offset,
                limit=request.limit or 200,
            )
        return telemetry_pb2.TelemetryRawResponse(points=[_row_to_raw_proto(r) for r in rows])

    async def GetTelemetrySnapshot(self, request, context):
        if not request.locomotive_id or not request.at:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "locomotive_id and at are required")
        factory = get_session_factory()
        async with factory() as session:
            rows = await telemetry_repository.query_snapshot(
                session,
                locomotive_id=request.locomotive_id,
                at=_parse_dt(request.at),
            )
        return telemetry_pb2.TelemetrySnapshotResponse(points=[_row_to_raw_proto(r) for r in rows])

    async def ListAlerts(self, request, context):
        factory = get_session_factory()
        async with factory() as session:
            rows = await alert_repository.find_many(
                session,
                locomotive_id=request.locomotive_id or None,
                severity=request.severity or None,
                acknowledged=request.acknowledged if request.filter_acknowledged else None,
                start=_parse_dt(request.start),
                end=_parse_dt(request.end),
                offset=request.offset,
                limit=request.limit or 50,
            )
        alerts = [_row_to_alert_proto(r) for r in rows]
        return telemetry_pb2.AlertsListResponse(alerts=alerts, total=len(alerts))

    async def GetAlert(self, request, context):
        factory = get_session_factory()
        async with factory() as session:
            row = await alert_repository.find_by_id(session, request.alert_id)
        if row is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"Alert {request.alert_id} not found")
        return _row_to_alert_proto(row)

    async def AcknowledgeAlert(self, request, context):
        factory = get_session_factory()
        async with factory() as session:
            await alert_repository.acknowledge(session, request.alert_id)
            row = await alert_repository.find_by_id(session, request.alert_id)
        if row is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"Alert {request.alert_id} not found")
        return _row_to_alert_proto(row)

    async def GetCurrentHealth(self, request, context):
        redis_raw = get_redis_raw()
        cached = await get_cached_health(redis_raw, request.locomotive_id)
        if cached:
            try:
                data = wire_decode(cached)
                return _dict_to_health_proto(data)
            except Exception:
                logger.warning("Failed to decode cached health, falling back to DB")

        factory = get_session_factory()
        async with factory() as session:
            rows = await health_repository.get_latest_readings(session, request.locomotive_id)
        if not rows:
            await context.abort(grpc.StatusCode.NOT_FOUND, "No telemetry data for this locomotive")

        return _compute_health_from_readings(request.locomotive_id, rows)

    async def GetHealthAt(self, request, context):
        factory = get_session_factory()
        async with factory() as session:
            row = await health_repository.get_snapshot_at(
                session,
                request.locomotive_id,
                _parse_dt(request.at),
            )
        if row is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, "No health data at this time")
        return _row_to_health_proto(row)

    async def GetFleetHealth(self, request, context):
        factory = get_session_factory()
        async with factory() as session:
            data = await health_repository.query_fleet_health(
                session,
                _parse_dt(request.start),
                _parse_dt(request.end),
            )
        return telemetry_pb2.FleetHealthResponse(
            stats=[
                telemetry_pb2.FleetHealthStats(
                    avg_score=data["avg_score"],
                    min_score=data["min_score"],
                    max_score=data["max_score"],
                    locomotive_count=data["total_locomotives"],
                    healthy_count=data["healthy_count"],
                    warning_count=data["warning_count"],
                    critical_count=data["critical_count"],
                ),
            ],
        )

    async def GetAlertFrequency(self, request, context):
        factory = get_session_factory()
        async with factory() as session:
            data = await alert_repository.query_fleet_alert_summary(
                session,
                _parse_dt(request.start),
                _parse_dt(request.end),
            )
        freqs = [
            telemetry_pb2.AlertFrequency(severity=sev, count=cnt) for sev, cnt in data.get("by_severity", {}).items()
        ]
        return telemetry_pb2.AlertFrequencyResponse(frequencies=freqs)

    async def GetSensorStats(self, request, context):
        factory = get_session_factory()
        async with factory() as session:
            stats = await telemetry_repository.query_sensor_stats(
                session,
                request.locomotive_id or None,
                _parse_dt(request.start),
                _parse_dt(request.end),
            )
            loco_type = ""
            if request.locomotive_id:
                loco_type = await telemetry_repository.query_locomotive_type(session, request.locomotive_id)
        return telemetry_pb2.SensorStatsResponse(
            stats=[
                telemetry_pb2.SensorStats(
                    sensor_type=s["sensor_type"],
                    unit=s["unit"],
                    avg=s["avg"],
                    min=s["min"],
                    max=s["max"],
                    stddev=s["stddev"],
                    samples=s["samples"],
                )
                for s in stats
            ],
            locomotive_type=loco_type,
        )

    async def GetHealthTrend(self, request, context):
        factory = get_session_factory()
        async with factory() as session:
            points = await health_repository.query_health_trend(
                session,
                request.locomotive_id or None,
                _parse_dt(request.start),
                _parse_dt(request.end),
            )
        return telemetry_pb2.HealthTrendResponse(
            points=[
                telemetry_pb2.HealthTrendPoint(
                    time=p["time"],
                    avg_score=p["avg_score"],
                    min_score=p["min_score"],
                    max_score=p["max_score"],
                )
                for p in points
            ],
        )

    async def GetLatestHealth(self, request, context):
        factory = get_session_factory()
        async with factory() as session:
            data = await health_repository.query_latest_health(
                session,
                request.locomotive_id or None,
                _parse_dt(request.start),
                _parse_dt(request.end),
            )
        factors = [
            telemetry_pb2.HealthFactor(
                sensor_type=f.get("sensor_type", ""),
                value=f.get("value", 0),
                unit=f.get("unit", ""),
                penalty=f.get("penalty", 0),
                contribution_pct=f.get("contribution_pct", 0),
                deviation_pct=f.get("deviation_pct", 0),
            )
            for f in (data.get("top_factors") or [])
            if isinstance(f, dict)
        ]
        return telemetry_pb2.LatestHealthResponse(
            avg_score=data["avg_score"],
            min_score=data["min_score"],
            max_score=data["max_score"],
            category=data["category"],
            damage_penalty=data["damage_penalty"],
            top_factors=factors,
        )

    async def GetWorstLocomotives(self, request, context):
        factory = get_session_factory()
        async with factory() as session:
            rows = await health_repository.query_worst_locomotives(
                session,
                _parse_dt(request.start),
                _parse_dt(request.end),
                limit=request.limit or 10,
            )
        return telemetry_pb2.WorstLocomotivesResponse(
            locomotives=[
                telemetry_pb2.WorstLocomotive(
                    locomotive_id=r["locomotive_id"],
                    locomotive_type=r["locomotive_type"],
                    serial_number=r["serial_number"],
                    avg_score=r["avg_score"],
                    min_score=r["min_score"],
                    max_score=r["max_score"],
                )
                for r in rows
            ],
        )

    async def GetFleetAlertSummary(self, request, context):
        factory = get_session_factory()
        async with factory() as session:
            data = await alert_repository.query_fleet_alert_summary(
                session,
                _parse_dt(request.start),
                _parse_dt(request.end),
            )
        return telemetry_pb2.FleetAlertSummaryResponse(
            total=data["total"],
            by_severity=data["by_severity"],
        )

    async def GetReportAlerts(self, request, context):
        factory = get_session_factory()
        async with factory() as session:
            rows = await alert_repository.query_alerts(
                session,
                request.locomotive_id or None,
                _parse_dt(request.start),
                _parse_dt(request.end),
            )
        return telemetry_pb2.ReportAlertsResponse(alerts=[_row_to_alert_proto(r) for r in rows])

    async def GetRawForAnomalies(self, request, context):
        factory = get_session_factory()
        async with factory() as session:
            rows = await telemetry_repository.query_raw_for_anomalies(
                session,
                request.locomotive_id,
                _parse_dt(request.start),
                _parse_dt(request.end),
            )
        return telemetry_pb2.RawForAnomaliesResponse(
            points=[
                telemetry_pb2.AnomalyDataPoint(
                    sensor_type=r["sensor_type"],
                    filtered_value=float(r["filtered_value"]),
                    time=r["time"].isoformat() if hasattr(r["time"], "isoformat") else str(r["time"]),
                )
                for r in rows
            ],
        )

    async def GetFleetLatestSnapshots(self, request, context):
        factory = get_session_factory()
        async with factory() as session:
            rows = await health_repository.query_fleet_latest_snapshots(session)
        return telemetry_pb2.FleetLatestSnapshotsResponse(
            entries=[
                telemetry_pb2.FleetSnapshotEntry(
                    locomotive_id=r["locomotive_id"],
                    locomotive_type=r["locomotive_type"],
                    score=r["score"],
                    category=r["category"],
                )
                for r in rows
            ],
        )

    async def GetUtilization(self, request, context):
        factory = get_session_factory()
        async with factory() as session:
            data = await telemetry_repository.query_utilization(
                session,
                request.locomotive_id or None,
                request.hours or 24,
            )
        return telemetry_pb2.UtilizationResponse(
            total_readings=data["total_readings"],
            active_readings=data["active_readings"],
            avg_speed=data["avg_speed"],
            max_speed=data["max_speed"],
        )


def _row_to_raw_proto(r: dict):
    return telemetry_pb2.TelemetryRawPoint(
        time=str(r.get("time") or r.get("timestamp", "")),
        locomotive_id=str(r["locomotive_id"]),
        locomotive_type=r.get("locomotive_type", ""),
        sensor_type=r["sensor_type"],
        value=float(r["value"]),
        filtered_value=float(r.get("filtered_value") or 0),
        unit=r.get("unit", ""),
        latitude=float(r.get("latitude") or 0),
        longitude=float(r.get("longitude") or 0),
    )


def _row_to_alert_proto(r: dict):
    return telemetry_pb2.AlertEvent(
        id=str(r["id"]),
        locomotive_id=str(r["locomotive_id"]),
        sensor_type=r["sensor_type"],
        severity=str(r["severity"]),
        value=float(r["value"]),
        threshold_min=float(r["threshold_min"]),
        threshold_max=float(r["threshold_max"]),
        message=r["message"],
        recommendation=r.get("recommendation", ""),
        timestamp=str(r["timestamp"]),
        acknowledged=bool(r["acknowledged"]),
    )


def _row_to_health_proto(r: dict):
    top_factors = r.get("top_factors") or []
    factors = [
        telemetry_pb2.HealthFactor(
            sensor_type=f.get("sensor_type", ""),
            value=f.get("value", 0),
            unit=f.get("unit", ""),
            penalty=f.get("penalty", 0),
            contribution_pct=f.get("contribution_pct", 0),
            deviation_pct=f.get("deviation_pct", 0),
        )
        for f in (top_factors if isinstance(top_factors, list) else [])
        if isinstance(f, dict)
    ]
    return telemetry_pb2.HealthSnapshot(
        locomotive_id=str(r.get("locomotive_id", "")),
        locomotive_type=r.get("locomotive_type", ""),
        overall_score=float(r.get("score", r.get("overall_score", 0))),
        category=r.get("category", ""),
        top_factors=factors,
        damage_penalty=float(r.get("damage_penalty", 0)),
        calculated_at=str(r.get("calculated_at", "")),
    )


def _dict_to_health_proto(d: dict):
    """Convert a wire-decoded Redis cache dict to protobuf."""
    factors = [
        telemetry_pb2.HealthFactor(
            sensor_type=f.get("sensor_type", ""),
            value=f.get("value", 0),
            unit=f.get("unit", ""),
            penalty=f.get("penalty", 0),
            contribution_pct=f.get("contribution_pct", 0),
            deviation_pct=f.get("deviation_pct", 0),
        )
        for f in d.get("top_factors", [])
        if isinstance(f, dict)
    ]
    return telemetry_pb2.HealthSnapshot(
        locomotive_id=str(d.get("locomotive_id", "")),
        locomotive_type=d.get("locomotive_type", ""),
        overall_score=float(d.get("overall_score", 0)),
        category=d.get("category", ""),
        top_factors=factors,
        damage_penalty=float(d.get("damage_penalty", 0)),
        calculated_at=str(d.get("calculated_at", "")),
    )


def _compute_health_from_readings(locomotive_id: str, rows: list[dict]):
    """Fallback health computation using default thresholds (mirrors processor)."""
    from shared.constants import DEFAULT_THRESHOLDS, HEALTH_WEIGHTS

    total_penalty = 0.0
    loco_type = rows[0].get("locomotive_type", "TE33A") if rows else "TE33A"
    factors = []

    for row in rows:
        sensor = row["sensor_type"]
        lo, hi = DEFAULT_THRESHOLDS.get(sensor, (0.0, 100.0))
        w = HEALTH_WEIGHTS.get(sensor, 0.05)
        value = row["value"]

        if lo <= value <= hi:
            mid = (lo + hi) / 2
            span = (hi - lo) / 2
            score = max(0.0, 1.0 - abs(value - mid) / span * 0.3) if span > 0 else 1.0
        elif value < lo:
            score = max(0.0, 1.0 - (lo - value) / max(lo, 1.0))
        else:
            score = max(0.0, 1.0 - (value - hi) / max(hi, 1.0))

        penalty = (1.0 - score) * w
        total_penalty += penalty
        factors.append(
            telemetry_pb2.HealthFactor(
                sensor_type=sensor,
                value=value,
                unit=row.get("unit", ""),
                penalty=round(penalty, 4),
            )
        )

    overall = max(0.0, min(100.0, 100.0 - total_penalty * 100.0))
    category = "Норма" if overall >= 80 else ("Внимание" if overall >= 50 else "Критично")

    factors.sort(key=lambda f: f.penalty, reverse=True)

    return telemetry_pb2.HealthSnapshot(
        locomotive_id=locomotive_id,
        locomotive_type=loco_type,
        overall_score=round(overall, 1),
        category=category,
        top_factors=factors[:5],
        damage_penalty=0.0,
        calculated_at=str(datetime.now(UTC)),
    )
