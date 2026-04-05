"""
Reusable async gRPC client for the Analytics Service.

HOW gRPC CHANNELS WORK:
  A gRPC channel is like a connection pool. You create it once at startup,
  and it manages HTTP/2 connections to the server automatically:
  - Multiplexing: multiple RPC calls share one TCP connection
  - Reconnection: auto-reconnects if the connection drops
  - Load balancing: can distribute across multiple server instances

  The Stub is a proxy object that exposes service methods as local functions.
  Calling stub.GetTelemetryBucketed(request) sends the request over the
  channel and returns the response — just like a local function call.

USAGE IN OTHER SERVICES:
  # In lifespan startup:
  client = AnalyticsClient("analytics-service:50051")
  await client.connect()
  app.state.analytics = client

  # In a route handler:
  result = await client.get_telemetry_bucketed(
      locomotive_id="...", start="2024-01-01T00:00:00", end="..."
  )

  # In lifespan shutdown:
  await client.close()

THIS PATTERN IS REUSABLE:
  For any new gRPC service, copy this pattern:
  1. Define .proto file
  2. Generate code (proto/generate.sh)
  3. Create a client wrapper like this one
  4. Add connect/close to lifespan
"""

from __future__ import annotations

import grpc.aio

from shared.generated import telemetry_pb2, telemetry_pb2_grpc
from shared.observability import get_logger

logger = get_logger(__name__)


class AnalyticsClient:
    """Async gRPC client for Analytics Service.

    Wraps the generated stub with:
    - Connection lifecycle management (connect/close)
    - Conversion from protobuf messages to Python dicts

    WHY WRAP THE STUB:
      The raw stub returns protobuf objects. Most of our code works with
      dicts and Pydantic models. This wrapper converts between them,
      so the rest of the codebase doesn't need to know about protobuf.
    """

    def __init__(self, target: str, *, timeout: float = 5.0):
        """
        Args:
            target: gRPC server address, e.g. "analytics-service:50051".
            timeout: Default timeout per RPC call in seconds.
        """
        self._target = target
        self._timeout = timeout
        self._channel: grpc.aio.Channel | None = None
        self._stub: telemetry_pb2_grpc.AnalyticsServiceStub | None = None

    async def connect(self) -> None:
        """Create gRPC channel and stub.

        insecure_channel = no TLS. Fine for internal Docker network.
        For production over public network, use secure_channel with certs.
        """
        self._channel = grpc.aio.insecure_channel(
            self._target,
            options=[
                # Send keepalive ping every 30s if idle
                ("grpc.keepalive_time_ms", 30_000),
                # Wait 10s for keepalive response
                ("grpc.keepalive_timeout_ms", 10_000),
                # Allow keepalive even with no active RPCs
                ("grpc.keepalive_permit_without_calls", True),
                # Max inbound message: 10 MB (default 4 MB).
                # Telemetry responses with 1000+ points can exceed 4 MB.
                ("grpc.max_receive_message_length", 10 * 1024 * 1024),
            ],
        )
        self._stub = telemetry_pb2_grpc.AnalyticsServiceStub(self._channel)
        logger.info("gRPC client connected", target=self._target)

    async def close(self) -> None:
        """Gracefully close the channel."""
        if self._channel:
            await self._channel.close()
            self._channel = None
            self._stub = None
            logger.info("gRPC client closed", target=self._target)

    @property
    def _s(self) -> telemetry_pb2_grpc.AnalyticsServiceStub:
        """Return the stub, raising if not connected."""
        if self._stub is None:
            msg = "gRPC client not connected. Call connect() first."
            raise RuntimeError(msg)
        return self._stub

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------

    async def get_telemetry_bucketed(
        self,
        *,
        locomotive_id: str = "",
        sensor_type: str = "",
        start: str = "",
        end: str = "",
        offset: int = 0,
        limit: int = 500,
    ) -> dict:
        """Query bucketed telemetry with auto-resolution.

        Returns dict: {points: list[dict], data_source: str, total_points: int}
        """
        resp = await self._s.GetTelemetryBucketed(
            telemetry_pb2.TelemetryBucketedRequest(
                locomotive_id=locomotive_id,
                sensor_type=sensor_type,
                start=start,
                end=end,
                offset=offset,
                limit=limit,
            ),
            timeout=self._timeout,
        )
        return {
            "points": [
                {
                    "bucket": p.bucket,
                    "locomotive_id": p.locomotive_id,
                    "sensor_type": p.sensor_type,
                    "avg_value": p.avg_value or None,
                    "min_value": p.min_value or None,
                    "max_value": p.max_value or None,
                    "last_value": p.last_value or None,
                    "unit": p.unit,
                }
                for p in resp.points
            ],
            "data_source": resp.data_source,
            "total_points": resp.total_points,
        }

    async def get_telemetry_raw(
        self,
        *,
        locomotive_id: str = "",
        sensor_type: str = "",
        start: str = "",
        end: str = "",
        offset: int = 0,
        limit: int = 200,
    ) -> list[dict]:
        resp = await self._s.GetTelemetryRaw(
            telemetry_pb2.TelemetryRawRequest(
                locomotive_id=locomotive_id,
                sensor_type=sensor_type,
                start=start,
                end=end,
                offset=offset,
                limit=limit,
            ),
            timeout=self._timeout,
        )
        return [_raw_point_to_dict(p) for p in resp.points]

    async def get_telemetry_snapshot(self, locomotive_id: str, at: str) -> list[dict]:
        resp = await self._s.GetTelemetrySnapshot(
            telemetry_pb2.TelemetrySnapshotRequest(locomotive_id=locomotive_id, at=at),
            timeout=self._timeout,
        )
        return [_raw_point_to_dict(p) for p in resp.points]

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    async def list_alerts(
        self,
        *,
        locomotive_id: str = "",
        severity: str = "",
        acknowledged: bool | None = None,
        start: str = "",
        end: str = "",
        offset: int = 0,
        limit: int = 50,
    ) -> dict:
        resp = await self._s.ListAlerts(
            telemetry_pb2.AlertsListRequest(
                locomotive_id=locomotive_id,
                severity=severity,
                filter_acknowledged=acknowledged is not None,
                acknowledged=acknowledged or False,
                start=start,
                end=end,
                offset=offset,
                limit=limit,
            ),
            timeout=self._timeout,
        )
        return {
            "alerts": [_alert_to_dict(a) for a in resp.alerts],
            "total": resp.total,
        }

    async def get_alert(self, alert_id: str) -> dict:
        resp = await self._s.GetAlert(
            telemetry_pb2.AlertGetRequest(alert_id=alert_id),
            timeout=self._timeout,
        )
        return _alert_to_dict(resp)

    async def acknowledge_alert(self, alert_id: str) -> dict:
        resp = await self._s.AcknowledgeAlert(
            telemetry_pb2.AlertAcknowledgeRequest(alert_id=alert_id),
            timeout=self._timeout,
        )
        return _alert_to_dict(resp)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def get_current_health(self, locomotive_id: str) -> dict:
        resp = await self._s.GetCurrentHealth(
            telemetry_pb2.HealthCurrentRequest(locomotive_id=locomotive_id),
            timeout=self._timeout,
        )
        return _health_to_dict(resp)

    async def get_health_at(self, locomotive_id: str, at: str) -> dict:
        resp = await self._s.GetHealthAt(
            telemetry_pb2.HealthAtRequest(locomotive_id=locomotive_id, at=at),
            timeout=self._timeout,
        )
        return _health_to_dict(resp)

    # ------------------------------------------------------------------
    # Fleet analytics
    # ------------------------------------------------------------------

    async def get_fleet_health(
        self,
        start: str,
        end: str,
        locomotive_type: str = "",
    ) -> list[dict]:
        resp = await self._s.GetFleetHealth(
            telemetry_pb2.FleetHealthRequest(start=start, end=end, locomotive_type=locomotive_type),
            timeout=self._timeout,
        )
        return [
            {
                "bucket": s.bucket,
                "locomotive_type": s.locomotive_type,
                "avg_score": s.avg_score,
                "min_score": s.min_score,
                "max_score": s.max_score,
                "stddev_score": s.stddev_score,
                "locomotive_count": s.locomotive_count,
                "healthy_count": s.healthy_count,
                "warning_count": s.warning_count,
                "critical_count": s.critical_count,
            }
            for s in resp.stats
        ]

    async def get_alert_frequency(
        self,
        start: str,
        end: str,
        sensor_type: str = "",
        severity: str = "",
    ) -> list[dict]:
        resp = await self._s.GetAlertFrequency(
            telemetry_pb2.AlertFrequencyRequest(start=start, end=end, sensor_type=sensor_type, severity=severity),
            timeout=self._timeout,
        )
        return [
            {"bucket": f.bucket, "sensor_type": f.sensor_type, "severity": f.severity, "count": f.count}
            for f in resp.frequencies
        ]

    # ------------------------------------------------------------------
    # Report-oriented queries
    # ------------------------------------------------------------------

    async def get_sensor_stats(self, *, locomotive_id: str = "", start: str = "", end: str = "") -> dict:
        resp = await self._s.GetSensorStats(
            telemetry_pb2.SensorStatsRequest(locomotive_id=locomotive_id, start=start, end=end),
            timeout=self._timeout,
        )
        return {
            "stats": [
                {
                    "sensor_type": s.sensor_type,
                    "unit": s.unit,
                    "avg": s.avg,
                    "min": s.min,
                    "max": s.max,
                    "stddev": s.stddev,
                    "samples": s.samples,
                }
                for s in resp.stats
            ],
            "locomotive_type": resp.locomotive_type,
        }

    async def get_health_trend(self, *, locomotive_id: str = "", start: str = "", end: str = "") -> list[dict]:
        resp = await self._s.GetHealthTrend(
            telemetry_pb2.HealthTrendRequest(locomotive_id=locomotive_id, start=start, end=end),
            timeout=self._timeout,
        )
        return [
            {"time": p.time, "avg_score": p.avg_score, "min_score": p.min_score, "max_score": p.max_score}
            for p in resp.points
        ]

    async def get_latest_health(self, *, locomotive_id: str = "", start: str = "", end: str = "") -> dict:
        resp = await self._s.GetLatestHealth(
            telemetry_pb2.LatestHealthRequest(locomotive_id=locomotive_id, start=start, end=end),
            timeout=self._timeout,
        )
        return {
            "avg_score": resp.avg_score,
            "min_score": resp.min_score,
            "max_score": resp.max_score,
            "category": resp.category,
            "damage_penalty": resp.damage_penalty,
            "top_factors": [
                {
                    "sensor_type": f.sensor_type,
                    "value": f.value,
                    "unit": f.unit,
                    "penalty": f.penalty,
                    "contribution_pct": f.contribution_pct,
                    "deviation_pct": f.deviation_pct,
                }
                for f in resp.top_factors
            ],
        }

    async def get_worst_locomotives(self, *, start: str, end: str, limit: int = 10) -> list[dict]:
        resp = await self._s.GetWorstLocomotives(
            telemetry_pb2.WorstLocomotivesRequest(start=start, end=end, limit=limit),
            timeout=self._timeout,
        )
        return [
            {
                "locomotive_id": loco.locomotive_id,
                "locomotive_type": loco.locomotive_type,
                "serial_number": loco.serial_number,
                "avg_score": loco.avg_score,
                "min_score": loco.min_score,
                "max_score": loco.max_score,
            }
            for loco in resp.locomotives
        ]

    async def get_fleet_alert_summary(self, *, start: str, end: str) -> dict:
        resp = await self._s.GetFleetAlertSummary(
            telemetry_pb2.FleetAlertSummaryRequest(start=start, end=end),
            timeout=self._timeout,
        )
        return {"total": resp.total, "by_severity": dict(resp.by_severity)}

    async def get_report_alerts(self, *, locomotive_id: str = "", start: str = "", end: str = "") -> list[dict]:
        resp = await self._s.GetReportAlerts(
            telemetry_pb2.ReportAlertsRequest(locomotive_id=locomotive_id, start=start, end=end),
            timeout=self._timeout,
        )
        return [_alert_to_dict(a) for a in resp.alerts]

    async def get_raw_for_anomalies(self, *, locomotive_id: str, start: str, end: str) -> list[dict]:
        resp = await self._s.GetRawForAnomalies(
            telemetry_pb2.RawForAnomaliesRequest(locomotive_id=locomotive_id, start=start, end=end),
            timeout=self._timeout,
        )
        return [{"sensor_type": p.sensor_type, "filtered_value": p.filtered_value, "time": p.time} for p in resp.points]

    async def get_fleet_latest_snapshots(self) -> list[dict]:
        resp = await self._s.GetFleetLatestSnapshots(
            telemetry_pb2.Empty(),
            timeout=self._timeout,
        )
        return [
            {
                "locomotive_id": e.locomotive_id,
                "locomotive_type": e.locomotive_type,
                "score": e.score,
                "category": e.category,
            }
            for e in resp.entries
        ]

    async def get_utilization(self, *, locomotive_id: str = "", hours: int = 24) -> dict:
        resp = await self._s.GetUtilization(
            telemetry_pb2.UtilizationRequest(locomotive_id=locomotive_id, hours=hours),
            timeout=self._timeout,
        )
        return {
            "total_readings": resp.total_readings,
            "active_readings": resp.active_readings,
            "avg_speed": resp.avg_speed,
            "max_speed": resp.max_speed,
        }


# ------------------------------------------------------------------
# Protobuf → dict converters (private)
# ------------------------------------------------------------------


def _raw_point_to_dict(p: telemetry_pb2.TelemetryRawPoint) -> dict:
    return {
        "time": p.time,
        "locomotive_id": p.locomotive_id,
        "locomotive_type": p.locomotive_type,
        "sensor_type": p.sensor_type,
        "value": p.value,
        "filtered_value": p.filtered_value,
        "unit": p.unit,
        "latitude": p.latitude or None,
        "longitude": p.longitude or None,
    }


def _alert_to_dict(a: telemetry_pb2.AlertEvent) -> dict:
    return {
        "id": a.id,
        "locomotive_id": a.locomotive_id,
        "sensor_type": a.sensor_type,
        "severity": a.severity,
        "value": a.value,
        "threshold_min": a.threshold_min,
        "threshold_max": a.threshold_max,
        "message": a.message,
        "recommendation": a.recommendation,
        "timestamp": a.timestamp,
        "acknowledged": a.acknowledged,
    }


def _health_to_dict(h: telemetry_pb2.HealthSnapshot) -> dict:
    return {
        "locomotive_id": h.locomotive_id,
        "locomotive_type": h.locomotive_type,
        "overall_score": h.overall_score,
        "category": h.category,
        "top_factors": [
            {
                "sensor_type": f.sensor_type,
                "value": f.value,
                "unit": f.unit,
                "penalty": f.penalty,
                "contribution_pct": f.contribution_pct,
                "deviation_pct": f.deviation_pct,
            }
            for f in h.top_factors
        ],
        "damage_penalty": h.damage_penalty,
        "calculated_at": h.calculated_at,
    }
