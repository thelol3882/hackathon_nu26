"""Routes endpoint — exposes the canonical railway polylines + stations.

This data is **static** for the lifetime of the process: the routes
are generated once at module import time by ``shared.route_geometry``
(deterministic synthetic polylines, see that module's docstring) and
both this gateway and the simulator load the exact same numbers.

The dashboard's RouteMap fetches /routes once on mount and uses the
result to render polylines and station markers under each locomotive.
A simple ``Cache-Control`` header lets the browser cache the response
for the rest of the session.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from shared.route_geometry import ROUTES

router = APIRouter()


class StationDTO(BaseModel):
    name: str
    lat: float
    lon: float
    km_from_start: float


class RouteDTO(BaseModel):
    name: str
    electrified: bool
    length_km: float
    # Polyline encoded as a list of [lat, lon] pairs (not objects) so the
    # JSON is small and react-leaflet can pass it straight to <Polyline>.
    waypoints: list[tuple[float, float]]
    stations: list[StationDTO]


def _to_dto(route) -> RouteDTO:
    return RouteDTO(
        name=route.name,
        electrified=route.electrified,
        length_km=round(route.length_m / 1000.0, 1),
        waypoints=route.waypoints,
        stations=[
            StationDTO(
                name=s.name,
                lat=s.lat,
                lon=s.lon,
                km_from_start=round(s.km_from_start, 1),
            )
            for s in route.stations
        ],
    )


# Pre-build the response once — routes never change at runtime.
_CACHED_PAYLOAD: list[RouteDTO] = [_to_dto(r) for r in ROUTES]


@router.get("/", response_model=list[RouteDTO])
async def list_routes() -> list[RouteDTO]:
    """All railway routes with their polylines and stations."""
    return _CACHED_PAYLOAD
