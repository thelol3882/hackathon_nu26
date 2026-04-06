"""Routes endpoint exposing static railway polylines and stations."""

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
    # [lat, lon] pairs so react-leaflet can pass directly to <Polyline>.
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


_CACHED_PAYLOAD: list[RouteDTO] = [_to_dto(r) for r in ROUTES]


@router.get("/", response_model=list[RouteDTO])
async def list_routes() -> list[RouteDTO]:
    """All railway routes with their polylines and stations."""
    return _CACHED_PAYLOAD
