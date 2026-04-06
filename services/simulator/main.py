"""Simulator service — generates realistic telemetry for locomotive fleet."""

import asyncio
import contextlib

from fastapi import FastAPI, HTTPException, Query

from shared.observability import setup_observability
from shared.observability.prometheus import setup_prometheus
from simulator.runner import runner

app = FastAPI(title="Locomotive Telemetry Simulator", version="0.1.0")

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


@app.get("/health")
async def health() -> dict:
    return {
        "status": "running" if runner.running else "stopped",
        "fleet_size": len(runner.fleet),
        "scenario": runner.scenario,
    }


@app.get("/metrics-stats")
async def metrics_stats() -> dict:
    return runner.get_metrics()


@app.post("/scenario/{name}")
async def switch_scenario(name: str) -> dict:
    try:
        runner.switch_scenario(name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return {"status": "ok", "scenario": name}


@app.post("/fleet/resize")
async def resize_fleet(n: int = Query(ge=1, le=5000)) -> dict:
    runner.resize_fleet(n)
    return {"status": "ok", "fleet_size": n}


@app.get("/fleet/sample")
async def sample_fleet(n: int = Query(default=5, ge=1, le=50)) -> list[dict]:
    return runner.sample_fleet(n)


@app.post("/burst")
async def burst(
    multiplier: float = Query(default=10.0, ge=1.0, le=100.0),
    duration: float = Query(default=60.0, ge=1.0, le=600.0),
) -> dict:
    runner.set_burst(multiplier, duration)
    return {"status": "ok", "multiplier": multiplier, "duration": duration}
