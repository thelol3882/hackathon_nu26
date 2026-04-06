"""Thin HTTP proxy to the internal simulator service."""

from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request

from api_gateway.core.config import get_settings

router = APIRouter()
settings = get_settings()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.simulator_http_url,
        timeout=settings.simulator_http_timeout,
    )


async def _forward(method: str, path: str, **kwargs: Any) -> Any:
    """Forward to the simulator, re-raising errors as HTTPException."""
    try:
        async with _client() as c:
            r = await c.request(method, path, **kwargs)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Simulator unreachable: {e}") from e
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text
        raise HTTPException(status_code=r.status_code, detail=detail)
    if r.status_code == 204 or not r.content:
        return None
    return r.json()


@router.get("/locomotives")
async def list_locomotives() -> list[dict]:
    """All locomotives currently being simulated."""
    return await _forward("GET", "/locomotives") or []


@router.get("/locomotives/{loco_id}")
async def get_locomotive(loco_id: UUID) -> dict:
    return await _forward("GET", f"/locomotives/{loco_id}")


@router.get("/health")
async def simulator_health() -> dict:
    return await _forward("GET", "/health")


@router.get("/metrics-stats")
async def simulator_metrics() -> dict:
    return await _forward("GET", "/metrics-stats")


@router.post("/locomotives", status_code=201)
async def create_locomotive(req: Request) -> dict:
    """Materialise a new locomotive in the simulator (body passed through)."""
    body = await req.json()
    return await _forward("POST", "/locomotives", json=body)


@router.patch("/locomotives/{loco_id}")
async def patch_locomotive(loco_id: UUID, req: Request) -> dict:
    body = await req.json()
    return await _forward("PATCH", f"/locomotives/{loco_id}", json=body)


@router.delete("/locomotives/{loco_id}", status_code=204)
async def delete_locomotive(loco_id: UUID) -> None:
    await _forward("DELETE", f"/locomotives/{loco_id}")
