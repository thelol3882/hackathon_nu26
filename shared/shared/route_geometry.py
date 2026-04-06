"""Route geometry: polylines + stations shared by simulator and API gateway.

Canonical source of truth for railway routes. Both simulator and gateway
import ``ROUTES`` so they always agree on geometry.

Resolution order per route: real OSM geometry from
``shared/data/routes/<slug>.geojson`` if present, otherwise a deterministic
synthetic polyline built by walking start->end with perpendicular jitter and
two smoothing passes. Stations likewise prefer OSM names, else synthetic
"Разъезд X км" ("Siding X km") km-posts. Deterministic per route name so
simulator and gateway compute identical results independently.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

# Mean earth radius; good enough for haversine at intra-country scale.
_EARTH_RADIUS_M = 6_371_000.0


def _find_geojson_dir() -> Path:
    """Locate shared/data/routes. Tries KTZ_ROUTES_DIR, the natural repo
    layout, the Docker wheel layout (/app/shared/data/routes), and CWD.
    First hit wins; falls through to candidates[0] so is_file() cleanly
    returns False rather than crashing on import."""
    import os

    candidates: list[Path] = []
    env = os.environ.get("KTZ_ROUTES_DIR")
    if env:
        candidates.append(Path(env))
    here = Path(__file__).resolve()
    # Repo install: .../shared/shared/route_geometry.py -> repo/shared/data/routes
    candidates.append(here.parent.parent.parent / "shared" / "data" / "routes")
    # Wheel install under .venv inside Docker image
    candidates.append(Path("/app/shared/data/routes"))
    candidates.append(Path.cwd() / "shared" / "data" / "routes")

    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


_GEOJSON_DIR = _find_geojson_dir()


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial compass bearing p1 -> p2 in degrees (0 = N, 90 = E)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _seeded_rng(name: str) -> random.Random:
    """Per-route RNG seeded from md5(name) so every process agrees.

    Python's ``hash()`` is randomised per interpreter (PYTHONHASHSEED),
    which would cause two services to generate different polylines for
    the same route name. md5 is just used for stable bytes; not security.
    """
    digest = hashlib.md5(name.encode("utf-8"), usedforsecurity=False).digest()
    seed = int.from_bytes(digest[:4], "big")
    return random.Random(seed)  # noqa: S311


def generate_polyline(
    name: str,
    lat_start: float,
    lon_start: float,
    lat_end: float,
    lon_end: float,
    *,
    n_segments: int = 14,
    jitter_deg: float = 0.35,
) -> list[tuple[float, float]]:
    """Build a believable hand-drawn-looking railway polyline.

    Walks start->end in ``n_segments`` steps, adds bell-enveloped
    perpendicular jitter at interior points, then applies two passes of
    neighbour smoothing. Returns n_segments+1 points with exact endpoints.
    """
    rng = _seeded_rng(name)

    # Direction as lat/lon-space unit vector; fine at this scale.
    dlat = lat_end - lat_start
    dlon = lon_end - lon_start
    length = math.hypot(dlat, dlon)
    if length == 0:
        return [(lat_start, lon_start), (lat_end, lon_end)]

    # Perpendicular unit vector (rotate 90°).
    perp_lat = -dlon / length
    perp_lon = dlat / length

    points: list[tuple[float, float]] = []
    for i in range(n_segments + 1):
        t = i / n_segments
        base_lat = lat_start + dlat * t
        base_lon = lon_start + dlon * t
        if 0 < i < n_segments:
            # Bell-shaped envelope: larger offsets mid-route, zero at endpoints.
            envelope = math.sin(math.pi * t)
            offset = rng.uniform(-jitter_deg, jitter_deg) * envelope
            base_lat += perp_lat * offset
            base_lon += perp_lon * offset
        points.append((base_lat, base_lon))

    # Two neighbour-smoothing passes so transitions are gentle, not jagged.
    for _ in range(2):
        smoothed = [points[0]]
        for i in range(1, len(points) - 1):
            a = points[i - 1]
            b = points[i]
            c = points[i + 1]
            smoothed.append(
                (
                    (a[0] + 2 * b[0] + c[0]) / 4,
                    (a[1] + 2 * b[1] + c[1]) / 4,
                )
            )
        smoothed.append(points[-1])
        points = smoothed

    return points


def cumulative_distances(points: list[tuple[float, float]]) -> list[float]:
    """Prefix-sum of segment lengths in metres; cum[0]=0, cum[-1]=total length."""
    cum = [0.0]
    for (lat1, lon1), (lat2, lon2) in pairwise(points):
        cum.append(cum[-1] + haversine_m(lat1, lon1, lat2, lon2))
    return cum


def position_at_distance(
    points: list[tuple[float, float]],
    cum: list[float],
    distance_m: float,
) -> tuple[float, float, float]:
    """Return (lat, lon, bearing_deg) at a cumulative distance. Clamps to endpoints."""
    if not points:
        return 0.0, 0.0, 0.0
    if distance_m <= 0:
        b = bearing_deg(points[0][0], points[0][1], points[1][0], points[1][1]) if len(points) > 1 else 0.0
        return points[0][0], points[0][1], b
    total = cum[-1]
    if distance_m >= total:
        b = bearing_deg(points[-2][0], points[-2][1], points[-1][0], points[-1][1]) if len(points) > 1 else 0.0
        return points[-1][0], points[-1][1], b

    # Linear scan is fine — polylines have ~16 points. Swap for
    # bisect.bisect_right(cum, distance_m) - 1 if this becomes hot.
    for i in range(1, len(cum)):
        if cum[i] >= distance_m:
            seg_start = cum[i - 1]
            seg_len = cum[i] - seg_start
            t = (distance_m - seg_start) / seg_len if seg_len > 0 else 0.0
            lat1, lon1 = points[i - 1]
            lat2, lon2 = points[i]
            return (
                lat1 + (lat2 - lat1) * t,
                lon1 + (lon2 - lon1) * t,
                bearing_deg(lat1, lon1, lat2, lon2),
            )

    return points[-1][0], points[-1][1], 0.0


@dataclass(frozen=True)
class Station:
    name: str
    lat: float
    lon: float
    km_from_start: float


def generate_stations(
    name: str,
    points: list[tuple[float, float]],
    cum: list[float],
    *,
    target_count: int = 6,
) -> list[Station]:
    """Place ``target_count`` synthetic km-post stations along the polyline.

    Evenly spaced by distance (skipping termini) with ±20% jitter so the
    grid doesn't look mechanical. Named "Разъезд X км" ("Siding X km"),
    matching the Soviet/KTZ naming convention.
    """
    if target_count <= 0 or len(points) < 2:
        return []
    rng = _seeded_rng(f"{name}::stations")
    total_m = cum[-1]
    if total_m <= 0:
        return []
    spacing_m = total_m / (target_count + 1)

    stations: list[Station] = []
    for i in range(1, target_count + 1):
        nominal = i * spacing_m
        shift = rng.uniform(-spacing_m * 0.2, spacing_m * 0.2)
        d = max(0.0, min(total_m, nominal + shift))
        lat, lon, _ = position_at_distance(points, cum, d)
        km = round(d / 1000.0)
        stations.append(
            Station(
                name=f"Разъезд {km} км",
                lat=lat,
                lon=lon,
                km_from_start=d / 1000.0,
            )
        )
    return stations


def _slugify(name: str) -> str:
    """Mirror of tools/import_osm_railways.py's slugify for geojson lookup."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _load_geojson_route(
    name: str,
) -> tuple[list[tuple[float, float]], list[Station]] | None:
    """Load OSM-derived geometry from shared/data/routes/<slug>.geojson.

    Returns (waypoints, stations) or None when the file is absent; the
    caller then falls back to the synthetic generator.
    """
    path = _GEOJSON_DIR / f"{_slugify(name)}.geojson"
    if not path.is_file():
        return None
    try:
        feature = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    geometry = feature.get("geometry", {})
    if geometry.get("type") != "LineString":
        return None
    coords = geometry.get("coordinates") or []
    # GeoJSON uses [lon, lat]; in-process convention is (lat, lon).
    waypoints: list[tuple[float, float]] = [(float(lat), float(lon)) for lon, lat in coords]
    if len(waypoints) < 2:
        return None

    props = feature.get("properties", {}) or {}
    stations: list[Station] = []
    for s in props.get("stations") or []:
        try:
            stations.append(
                Station(
                    name=str(s["name"]),
                    lat=float(s["lat"]),
                    lon=float(s["lon"]),
                    km_from_start=float(s["km_from_start"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    return waypoints, stations


@dataclass
class Route:
    """Canonical route. waypoints/stations/length_m are computed in
    __post_init__ so callers only need the start/end pair."""

    name: str
    lat_start: float
    lon_start: float
    lat_end: float
    lon_end: float
    electrified: bool

    waypoints: list[tuple[float, float]] = field(default_factory=list)
    cum_distances_m: list[float] = field(default_factory=list)
    stations: list[Station] = field(default_factory=list)
    length_m: float = 0.0

    def __post_init__(self) -> None:
        # Resolution order: explicit waypoints -> OSM geojson -> synthetic.
        if not self.waypoints:
            geo = _load_geojson_route(self.name)
            if geo is not None:
                self.waypoints, geo_stations = geo
                # Prefer real OSM station names over synthetic placeholders,
                # but never override stations the caller supplied explicitly.
                if not self.stations and geo_stations:
                    self.stations = geo_stations
            else:
                self.waypoints = generate_polyline(
                    self.name,
                    self.lat_start,
                    self.lon_start,
                    self.lat_end,
                    self.lon_end,
                )
        self.cum_distances_m = cumulative_distances(self.waypoints)
        self.length_m = self.cum_distances_m[-1] if self.cum_distances_m else 0.0
        if not self.stations:
            self.stations = generate_stations(self.name, self.waypoints, self.cum_distances_m)

    def position_at(self, distance_m: float) -> tuple[float, float, float]:
        """(lat, lon, bearing) at the given distance along the route."""
        return position_at_distance(self.waypoints, self.cum_distances_m, distance_m)


# Real Kazakhstan railway corridors. Geometry comes from OSM geojson when
# available, otherwise a synthetic polyline (see module docstring).
ROUTES: list[Route] = [
    Route("Almaty-Astana", 43.26, 76.95, 51.16, 71.47, electrified=True),
    Route("Astana-Petropavlovsk", 51.16, 71.47, 54.86, 69.14, electrified=False),
    Route("Astana-Ekibastuz", 51.16, 71.47, 51.72, 75.32, electrified=False),
    Route("Almaty-Shymkent", 43.26, 76.95, 42.34, 69.59, electrified=True),
    Route("Shymkent-Turkestan", 42.34, 69.59, 43.29, 68.27, electrified=False),
    Route("Ekibastuz-Pavlodar", 51.72, 75.32, 52.28, 76.97, electrified=False),
    Route("Aktobe-Atyrau", 50.28, 57.20, 47.12, 51.88, electrified=False),
    Route("Aktobe-Kostanay", 50.28, 57.20, 53.21, 63.62, electrified=False),
    Route("Almaty-Balkhash", 43.26, 76.95, 46.84, 74.98, electrified=False),
    Route("Astana-Kokshetau", 51.16, 71.47, 53.28, 69.39, electrified=False),
]


def get_route(name: str) -> Route | None:
    for r in ROUTES:
        if r.name == name:
            return r
    return None
