"""Simulator service — operator-managed locomotive sandbox.

Boots empty. The dashboard creates locomotives one at a time, each
with its own route, sub-segment between two stations, scenario and
mode. There's no fleet-wide scenario any more; each locomotive owns
its own runtime state.

The HTTP surface is intentionally minimal:

  GET    /health                       — liveness + simple stats
  GET    /metrics-stats                — runner counters
  GET    /locomotives                  — list everything currently simulated
  GET    /locomotives/{id}             — one locomotive's full state
  POST   /locomotives                  — add a new locomotive
  PATCH  /locomotives/{id}             — partial update
  DELETE /locomotives/{id}             — remove from the fleet
  POST   /burst                        — kept for load-testing convenience

No authentication. The simulator runs internal-only behind the
api-gateway, which the operator hits with admin auth — see
``services/api-gateway/api_gateway/api/router_simulator.py``.
"""

import asyncio
import contextlib
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from shared.enums import LocomotiveType
from shared.observability import setup_observability
from shared.observability.prometheus import setup_prometheus
from shared.route_geometry import ROUTES, get_route
from simulator.models.locomotive_state import (
    LocomotiveMode,
    LocomotiveScenario,
    LocomotiveState,
    OnArrival,
)
from simulator.runner import LocomotiveNotFoundError, runner

app = FastAPI(title="Locomotive Telemetry Simulator", version="0.2.0")

app.state.shutdown_otel = setup_observability(app, service_name="simulator")
setup_prometheus(app, service_name="simulator")

_runner_task: asyncio.Task | None = None


@app.on_event("startup")
async def startup() -> None:
    global _runner_task
    runner.init_fleet()
    _runner_task = asyncio.create_task(runner.run())


@app.on_event("shutdown")
async def shutdown() -> None:
    runner.stop()
    if _runner_task:
        _runner_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _runner_task
    app.state.shutdown_otel()


# ---------------------------------------------------------------------------
# Health / metrics
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    return {
        "status": "running" if runner.running else "stopped",
        "fleet_size": len(runner.fleet),
    }


@app.get("/metrics-stats")
async def metrics_stats() -> dict:
    return runner.get_metrics()


@app.post("/burst")
async def burst(
    multiplier: Annotated[float, Query(ge=1.0, le=100.0)] = 10.0,
    duration: Annotated[float, Query(ge=1.0, le=600.0)] = 60.0,
) -> dict:
    """Multiply tick rate by ``multiplier`` for ``duration`` seconds."""
    runner.set_burst(multiplier, duration)
    return {"status": "ok", "multiplier": multiplier, "duration": duration}


# ---------------------------------------------------------------------------
# Locomotive CRUD
# ---------------------------------------------------------------------------


class StationDTO(BaseModel):
    name: str
    km_from_start: float


class LocomotiveStateDTO(BaseModel):
    """What we hand back to the dashboard about one locomotive.

    The full ``LocomotiveState`` carries internal kinematics fields
    (``mode_ticks``, ``scenario_tick``, etc.) the UI shouldn't see.
    This DTO is the curated view.
    """

    id: UUID
    name: str
    loco_type: LocomotiveType
    route_name: str
    mode: LocomotiveMode
    scenario: LocomotiveScenario
    auto_mode: bool
    on_arrival: OnArrival
    speed_kmh: float
    forward: bool
    distance_km: float
    start_km: float
    end_km: float
    segment_progress: float
    lat: float
    lon: float
    bearing_deg: float


def _to_dto(state: LocomotiveState) -> LocomotiveStateDTO:
    return LocomotiveStateDTO(
        id=state.id,
        name=state.name,
        loco_type=state.loco_type,
        route_name=state.route.name,
        mode=state.mode,
        scenario=state.scenario,
        auto_mode=state.auto_mode,
        on_arrival=state.on_arrival,
        speed_kmh=round(state.speed, 2),
        forward=state.forward,
        distance_km=round(state.distance_m / 1000.0, 3),
        start_km=round(state.start_distance_m / 1000.0, 3),
        end_km=round(state.end_distance_m / 1000.0, 3),
        segment_progress=round(state.segment_progress, 4),
        lat=round(state.lat, 6),
        lon=round(state.lon, 6),
        bearing_deg=round(state.bearing_deg, 1),
    )


class CreateLocomotiveRequest(BaseModel):
    """Body for ``POST /locomotives``.

    ``id`` lets the dashboard supply the catalogue UUID it just got
    from the gateway's ``POST /locomotives``, so the simulation entry
    and the DB record line up. Stations are picked by name from the
    /routes catalogue; if either is omitted the locomotive runs the
    full route from end to end.
    """

    id: UUID
    loco_type: LocomotiveType
    route_name: str
    name: str = ""
    start_station: str | None = None
    end_station: str | None = None
    mode: LocomotiveMode = LocomotiveMode.DEPOT
    scenario: LocomotiveScenario = LocomotiveScenario.NORMAL
    on_arrival: OnArrival = OnArrival.LOOP
    auto_mode: bool = False
    initial_speed_kmh: float = Field(default=0.0, ge=0.0, le=200.0)


class UpdateLocomotiveRequest(BaseModel):
    """Body for ``PATCH /locomotives/{id}``. All fields optional."""

    name: str | None = None
    route_name: str | None = None
    start_station: str | None = None
    end_station: str | None = None
    mode: LocomotiveMode | None = None
    scenario: LocomotiveScenario | None = None
    on_arrival: OnArrival | None = None
    auto_mode: bool | None = None
    speed_kmh: float | None = Field(default=None, ge=0.0, le=200.0)


def _resolve_station_km(route_name: str, station_name: str | None) -> float | None:
    """Look up a station's km mark on a given route.

    Returns ``None`` when the station name is empty (caller falls back
    to the route's natural endpoint). Raises HTTPException 400 if the
    name is given but doesn't exist on the route — better a clean
    error than a silently wrong distance.
    """
    if not station_name:
        return None
    route = get_route(route_name)
    if route is None:
        raise HTTPException(status_code=400, detail=f"Unknown route: {route_name!r}")
    for s in route.stations:
        if s.name == station_name:
            return s.km_from_start
    raise HTTPException(
        status_code=400,
        detail=f"Station {station_name!r} not found on route {route_name!r}",
    )


@app.get("/locomotives", response_model=list[LocomotiveStateDTO])
async def list_locomotives() -> list[LocomotiveStateDTO]:
    return [_to_dto(s) for s in runner.list_locomotives()]


@app.get("/locomotives/{loco_id}", response_model=LocomotiveStateDTO)
async def get_locomotive(loco_id: UUID) -> LocomotiveStateDTO:
    try:
        return _to_dto(runner.get_locomotive(loco_id))
    except LocomotiveNotFoundError as e:
        raise HTTPException(status_code=404, detail="Locomotive not in simulator") from e


@app.post("/locomotives", response_model=LocomotiveStateDTO, status_code=201)
async def create_locomotive(body: CreateLocomotiveRequest) -> LocomotiveStateDTO:
    start_km = _resolve_station_km(body.route_name, body.start_station)
    end_km = _resolve_station_km(body.route_name, body.end_station)
    try:
        state = runner.add_locomotive(
            loco_id=body.id,
            loco_type=body.loco_type,
            route_name=body.route_name,
            name=body.name,
            start_km=start_km or 0.0,
            end_km=end_km,
            mode=body.mode,
            scenario=body.scenario,
            on_arrival=body.on_arrival,
            auto_mode=body.auto_mode,
            initial_speed_kmh=body.initial_speed_kmh,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return _to_dto(state)


@app.patch("/locomotives/{loco_id}", response_model=LocomotiveStateDTO)
async def patch_locomotive(loco_id: UUID, body: UpdateLocomotiveRequest) -> LocomotiveStateDTO:
    # If the caller is moving the loco to a new route AND naming
    # stations on it, those station lookups must use the new route.
    target_route = body.route_name
    if target_route is None:
        try:
            target_route = runner.get_locomotive(loco_id).route.name
        except LocomotiveNotFoundError as e:
            raise HTTPException(status_code=404, detail="Locomotive not in simulator") from e
    start_km = _resolve_station_km(target_route, body.start_station)
    end_km = _resolve_station_km(target_route, body.end_station)
    try:
        state = runner.update_locomotive(
            loco_id,
            route_name=body.route_name,
            start_km=start_km,
            end_km=end_km,
            mode=body.mode,
            scenario=body.scenario,
            on_arrival=body.on_arrival,
            auto_mode=body.auto_mode,
            speed_kmh=body.speed_kmh,
            name=body.name,
        )
    except LocomotiveNotFoundError as e:
        raise HTTPException(status_code=404, detail="Locomotive not in simulator") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return _to_dto(state)


@app.delete("/locomotives/{loco_id}", status_code=204)
async def delete_locomotive(loco_id: UUID) -> None:
    try:
        runner.remove_locomotive(loco_id)
    except LocomotiveNotFoundError as e:
        raise HTTPException(status_code=404, detail="Locomotive not in simulator") from e


# ---------------------------------------------------------------------------
# Routes catalogue (mirrors api-gateway /routes — handy for the simulator's
# own dry-runs and CLI scripts that want to know station positions)
# ---------------------------------------------------------------------------


class RouteSummaryDTO(BaseModel):
    name: str
    electrified: bool
    length_km: float
    stations: list[StationDTO]


@app.get("/routes", response_model=list[RouteSummaryDTO])
async def list_routes() -> list[RouteSummaryDTO]:
    return [
        RouteSummaryDTO(
            name=r.name,
            electrified=r.electrified,
            length_km=round(r.length_m / 1000.0, 1),
            stations=[
                StationDTO(name=s.name, km_from_start=round(s.km_from_start, 1))
                for s in r.stations
            ],
        )
        for r in ROUTES
    ]
