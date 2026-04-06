"""Import real KTZ railway polylines and stations from a Geofabrik PBF.

Run with::

    uv sync --group osm
    uv run python tools/import_osm_railways.py

What it does:

1. Downloads ``kazakhstan-latest.osm.pbf`` from Geofabrik (or reuses
   the cached copy under ``tools/.cache/``).
2. Parses it with pyosmium, collecting:

   * every ``railway=rail`` way with its full node geometry,
   * every ``railway=station`` / ``railway=halt`` node with its name.

3. Builds an undirected weighted graph where vertices are way
   *endpoint* nodes (the first and last node of each way) and edges
   are ways themselves, weighted by haversine length. Adjacent ways
   share endpoints in OSM, so this gives us a navigable rail network.
4. For each of our 10 KTZ corridors (start / end city) finds the
   nearest endpoint to each city, runs Dijkstra, and reconstructs the
   full polyline by stitching the geometries of the ways on the path.
5. Simplifies each polyline with Douglas-Peucker (~500 m tolerance) so
   we ship maybe 100-300 points per route instead of 5000+.
6. Attaches stations whose location lies within ``STATION_NEAR_M`` of
   the polyline. Picks Russian / Kazakh / English / default name in
   that order. Drops duplicates and sorts by distance from the start.
7. Writes one ``shared/data/routes/<slug>.geojson`` per route.

This is a one-shot dev tool — it does not run in production. The
results are committed to the repo. To refresh against newer Geofabrik
data, just delete ``tools/.cache/`` and re-run.
"""

from __future__ import annotations

import contextlib
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

import httpx
import networkx as nx
import osmium
from shapely.geometry import LineString, Point

# Force UTF-8 stdout for Windows so Cyrillic station names print
# without choking the codec.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "tools" / ".cache"
PBF_URL = "https://download.geofabrik.de/asia/kazakhstan-latest.osm.pbf"
PBF_PATH = CACHE_DIR / "kazakhstan-latest.osm.pbf"
OUTPUT_DIR = REPO_ROOT / "shared" / "data" / "routes"

# Tolerance for the Douglas-Peucker simplification, in degrees. ~0.005°
# is roughly 500 m at this latitude — visually indistinguishable on a
# country-scale map but cuts the point count by ~50x.
SIMPLIFY_TOL_DEG = 0.005

# A station node has to lie this close to the polyline to be considered
# part of the route. Real KTZ stations sit on the track, so 800 m of
# slack is plenty without picking up sidings on the wrong line.
STATION_NEAR_M = 800.0

# Up to this many stations per route. Cuts noise on long mainlines.
MAX_STATIONS_PER_ROUTE = 12

EARTH_R_M = 6_371_000.0

# Our 10 KTZ corridors. Endpoints are real cities; the polyline that
# connects them is what we're after.
KTZ_ROUTES: list[dict[str, Any]] = [
    {
        "name": "Almaty-Astana",
        "start": (43.26, 76.95),
        "end": (51.16, 71.47),
        "electrified": True,
    },
    {
        "name": "Astana-Petropavlovsk",
        "start": (51.16, 71.47),
        "end": (54.86, 69.14),
        "electrified": False,
    },
    {
        "name": "Astana-Ekibastuz",
        "start": (51.16, 71.47),
        "end": (51.72, 75.32),
        "electrified": False,
    },
    {
        "name": "Almaty-Shymkent",
        "start": (43.26, 76.95),
        "end": (42.34, 69.59),
        "electrified": True,
    },
    {
        "name": "Shymkent-Turkestan",
        "start": (42.34, 69.59),
        "end": (43.29, 68.27),
        "electrified": False,
    },
    {
        "name": "Ekibastuz-Pavlodar",
        "start": (51.72, 75.32),
        "end": (52.28, 76.97),
        "electrified": False,
    },
    {
        "name": "Aktobe-Atyrau",
        "start": (50.28, 57.20),
        "end": (47.12, 51.88),
        "electrified": False,
    },
    {
        "name": "Aktobe-Kostanay",
        "start": (50.28, 57.20),
        "end": (53.21, 63.62),
        "electrified": False,
    },
    {
        "name": "Almaty-Balkhash",
        "start": (43.26, 76.95),
        "end": (46.84, 74.98),
        "electrified": False,
    },
    {
        "name": "Astana-Kokshetau",
        "start": (51.16, 71.47),
        "end": (53.28, 69.39),
        "electrified": False,
    },
]


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_R_M * math.asin(math.sqrt(a))


def polyline_length_m(points: list[tuple[float, float]]) -> float:
    total = 0.0
    for (lat1, lon1), (lat2, lon2) in pairwise(points):
        total += haversine_m(lat1, lon1, lat2, lon2)
    return total


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ---------------------------------------------------------------------------
# PBF download
# ---------------------------------------------------------------------------


def ensure_pbf() -> Path:
    """Download the Kazakhstan PBF if not already cached."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if PBF_PATH.exists() and PBF_PATH.stat().st_size > 50_000_000:
        size_mb = PBF_PATH.stat().st_size / (1024 * 1024)
        print(f"[cache hit] {PBF_PATH.name} ({size_mb:.0f} MB)")
        return PBF_PATH

    print(f"[download] {PBF_URL}")
    print("This is ~120 MB and may take a few minutes...")
    t0 = time.monotonic()
    with httpx.Client(timeout=600, follow_redirects=True) as c, c.stream("GET", PBF_URL) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        last_log = 0.0
        with PBF_PATH.open("wb") as f:
            for chunk in r.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                if now - last_log > 2:
                    pct = (downloaded / total * 100) if total else 0
                    speed = downloaded / (now - t0) / 1024 / 1024
                    print(
                        f"  {downloaded / 1024 / 1024:.0f} / "
                        f"{total / 1024 / 1024:.0f} MB ({pct:.0f}%) at {speed:.1f} MB/s"
                    )
                    last_log = now
    dt = time.monotonic() - t0
    print(f"[done] downloaded in {dt:.0f}s")
    return PBF_PATH


# ---------------------------------------------------------------------------
# OSM parsing
# ---------------------------------------------------------------------------


@dataclass
class RailWay:
    osm_id: int
    nodes: list[tuple[float, float]]  # full geometry, lat/lon
    node_ids: list[int]  # for endpoint identity in the graph

    @property
    def length_m(self) -> float:
        return polyline_length_m(self.nodes)

    @property
    def first_node_id(self) -> int:
        return self.node_ids[0]

    @property
    def last_node_id(self) -> int:
        return self.node_ids[-1]


@dataclass
class StationNode:
    osm_id: int
    lat: float
    lon: float
    name: str
    kind: str  # 'station' or 'halt'


class RailwayHandler(osmium.SimpleHandler):
    """Streams the PBF, picks out rails and stations.

    pyosmium's NodeLocationsForWays back-end (enabled by passing
    ``locations=True`` to ``apply_file``) plugs node coordinates
    straight into the way callback, so we don't need a manual node
    cache. We still touch ``node()`` to harvest stations.
    """

    def __init__(self) -> None:
        super().__init__()
        self.rails: list[RailWay] = []
        self.stations: list[StationNode] = []

    def node(self, n: Any) -> None:
        rw = n.tags.get("railway")
        if rw not in ("station", "halt"):
            return
        # Pick best name in priority order — Russian first because
        # KTZ documentation primarily uses it, then Kazakh, then English.
        name = n.tags.get("name:ru") or n.tags.get("name") or n.tags.get("name:kk") or n.tags.get("name:en")
        if not name:
            return
        # Some nodes in PBFs lack coordinates (deleted history,
        # corruption, etc.) — skip them silently.
        with contextlib.suppress(osmium.InvalidLocationError):
            self.stations.append(
                StationNode(
                    osm_id=n.id,
                    lat=n.location.lat,
                    lon=n.location.lon,
                    name=str(name),
                    kind=str(rw),
                )
            )

    def way(self, w: Any) -> None:
        if w.tags.get("railway") != "rail":
            return
        try:
            geom = [(nd.lat, nd.lon) for nd in w.nodes]
            node_ids = [nd.ref for nd in w.nodes]
        except osmium.InvalidLocationError:
            return
        if len(geom) < 2:
            return
        self.rails.append(RailWay(osm_id=w.id, nodes=geom, node_ids=node_ids))


# ---------------------------------------------------------------------------
# Graph + path
# ---------------------------------------------------------------------------


def build_graph(rails: list[RailWay]) -> tuple[nx.MultiGraph, dict[int, tuple[float, float]]]:
    """Build a routable rail graph from OSM ways.

    The naive approach — using each way as a single edge between its
    first and last nodes — is broken on real OSM data because OSM
    ways aren't always split at junctions: a long way A may pass
    *through* a node that's also the endpoint of way B, and unless we
    treat that node as a vertex the two ways look disconnected.

    We do it the routing-engine way:

    1. Count how many times each node id appears across all rails.
    2. A node is a "junction" iff it's referenced by 2+ rail ways
       (or it's the very first/last node of a way, which is always
       a vertex by definition).
    3. For each way, split its node list at every junction and create
       one graph edge per resulting sub-segment, weighted by haversine
       length and carrying the sub-segment's geometry directly.

    Returns the graph and a node-id → (lat, lon) lookup populated for
    every junction node we created. The lookup is what ``nearest_node``
    searches against.
    """
    # Pass 1: how many times is each node referenced across rails?
    refcount: dict[int, int] = {}
    for w in rails:
        for nid in w.node_ids:
            refcount[nid] = refcount.get(nid, 0) + 1

    g: nx.MultiGraph = nx.MultiGraph()
    coord_by_node: dict[int, tuple[float, float]] = {}

    # Pass 2: split each way at junctions, emit one edge per sub-segment.
    for w in rails:
        n = len(w.node_ids)
        # Indices that should become graph vertices: every endpoint
        # of the way, plus every interior node referenced by another
        # way (refcount >= 2).
        split_idx = [i for i, nid in enumerate(w.node_ids) if i == 0 or i == n - 1 or refcount.get(nid, 0) >= 2]
        for i, j in pairwise(split_idx):
            sub_geom = w.nodes[i : j + 1]
            sub_ids = w.node_ids[i : j + 1]
            if len(sub_geom) < 2:
                continue
            length = polyline_length_m(sub_geom)
            if length <= 0:
                continue
            u, v = sub_ids[0], sub_ids[-1]
            if u == v:
                continue
            g.add_edge(
                u,
                v,
                weight=length,
                geom=sub_geom,
                u_id=u,
                v_id=v,
            )
            coord_by_node[u] = sub_geom[0]
            coord_by_node[v] = sub_geom[-1]

    return g, coord_by_node


def nearest_node(
    coord_by_node: dict[int, tuple[float, float]],
    lat: float,
    lon: float,
    *,
    allowed: set[int] | None = None,
) -> int | None:
    """Find the graph vertex closest to the given (lat, lon).

    Pass ``allowed`` to constrain the search to a subset of vertices
    — typically the largest connected component, so we never anchor
    a route to a stranded industrial siding that can't reach anywhere.

    Squared planar distance is monotone with haversine at country
    scale and ~10x cheaper.
    """
    best_node = None
    best_d = float("inf")
    for node_id, (la, lo) in coord_by_node.items():
        if allowed is not None and node_id not in allowed:
            continue
        d = (la - lat) ** 2 + (lo - lon) ** 2
        if d < best_d:
            best_d = d
            best_node = node_id
    return best_node


def stitch_polyline(g: nx.MultiGraph, path: list[int]) -> list[tuple[float, float]]:
    """Walk the Dijkstra path of node ids and concatenate edge geometries.

    Each edge carries its own sub-segment geometry (from
    ``build_graph``), so we no longer need to remember which way it
    came from — we just check whether the segment runs ``u → v`` or
    ``v → u`` and reverse if necessary.
    """
    if len(path) < 2:
        return []
    out: list[tuple[float, float]] = []
    for u, v in pairwise(path):
        edges = g.get_edge_data(u, v) or {}
        if not edges:
            continue
        # Pick the lightest parallel edge between u and v.
        best_key = min(edges, key=lambda k: edges[k]["weight"])
        edge = edges[best_key]
        geom: list[tuple[float, float]] = list(edge["geom"])
        # Orient the sub-segment so its head matches our current `u`.
        if edge["u_id"] == u:
            segment = geom
        elif edge["v_id"] == u:
            segment = list(reversed(geom))
        else:
            segment = geom  # shouldn't happen — bail safely

        if not out:
            out.extend(segment)
        else:
            # Drop the joint we already have at the tail.
            out.extend(segment[1:])
    return out


def simplify(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) < 3:
        return points
    # shapely takes (x, y) = (lon, lat); we keep our convention as
    # (lat, lon) so just swap on the way in and out.
    line = LineString([(lon, lat) for lat, lon in points])
    simplified = line.simplify(SIMPLIFY_TOL_DEG, preserve_topology=False)
    return [(lat, lon) for lon, lat in simplified.coords]


# ---------------------------------------------------------------------------
# Stations
# ---------------------------------------------------------------------------


def attach_stations(polyline: list[tuple[float, float]], stations: list[StationNode]) -> list[dict[str, Any]]:
    """Find stations close to the polyline, project them onto it, and
    return a list of {name, lat, lon, km_from_start} sorted by km."""
    if not polyline or not stations:
        return []
    line = LineString([(lon, lat) for lat, lon in polyline])
    total_len_m = polyline_length_m(polyline)
    if total_len_m <= 0:
        return []

    # Pre-compute a fast bbox so we don't run distance() against every
    # station in the country.
    lats = [p[0] for p in polyline]
    lons = [p[1] for p in polyline]
    pad_deg = 0.05  # ~5 km
    south, north = min(lats) - pad_deg, max(lats) + pad_deg
    west, east = min(lons) - pad_deg, max(lons) + pad_deg

    seen_names: set[str] = set()
    out: list[dict[str, Any]] = []
    for st in stations:
        if not (south <= st.lat <= north and west <= st.lon <= east):
            continue
        if st.name in seen_names:
            continue
        # Approximate metres-per-degree at this latitude. Good enough
        # for an inclusion test where we only care about the order of
        # magnitude.
        meters_per_deg = 111_000.0
        pt = Point(st.lon, st.lat)
        d_deg = line.distance(pt)
        d_m = d_deg * meters_per_deg
        if d_m > STATION_NEAR_M:
            continue
        # Project the station onto the polyline to get its km mark.
        proj_dist_deg = line.project(pt)
        # `project` returns a distance along the line in the input
        # CRS units (degrees here). Convert by ratio rather than
        # remeasuring in metres.
        if line.length <= 0:
            continue
        ratio = proj_dist_deg / line.length
        km_from_start = ratio * total_len_m / 1000.0

        seen_names.add(st.name)
        out.append(
            {
                "name": st.name,
                "lat": st.lat,
                "lon": st.lon,
                "km_from_start": round(km_from_start, 2),
            }
        )

    out.sort(key=lambda s: s["km_from_start"])
    if len(out) > MAX_STATIONS_PER_ROUTE:
        # Spread the kept stations evenly across the route instead of
        # truncating to the first N (which would all bunch on one end).
        step = len(out) / MAX_STATIONS_PER_ROUTE
        out = [out[int(i * step)] for i in range(MAX_STATIONS_PER_ROUTE)]
    return out


# ---------------------------------------------------------------------------
# GeoJSON output
# ---------------------------------------------------------------------------


def write_geojson(
    *,
    name: str,
    electrified: bool,
    polyline: list[tuple[float, float]],
    stations: list[dict[str, Any]],
    out_path: Path,
) -> None:
    length_km = polyline_length_m(polyline) / 1000.0
    feature = {
        "type": "Feature",
        "properties": {
            "name": name,
            "electrified": electrified,
            "length_km": round(length_km, 1),
            "stations": stations,
        },
        # GeoJSON spec uses [lon, lat] order — opposite of our internal
        # convention. Convert here so the file is standards-compliant.
        "geometry": {
            "type": "LineString",
            "coordinates": [[lon, lat] for lat, lon in polyline],
        },
    }
    out_path.write_text(json.dumps(feature, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pbf = ensure_pbf()

    print("\n[parse] reading PBF (this takes ~30-60s)...")
    t0 = time.monotonic()
    handler = RailwayHandler()
    handler.apply_file(str(pbf), locations=True, idx="flex_mem")
    dt = time.monotonic() - t0
    print(f"[parse] done in {dt:.0f}s — {len(handler.rails)} rails, {len(handler.stations)} stations")

    print("\n[graph] building rail network...")
    t0 = time.monotonic()
    g, coord_by_node = build_graph(handler.rails)
    # Restrict the start/end search to the largest connected component
    # so we never anchor a route to a stranded industrial spur that
    # has no path to the rest of the network.
    biggest_component: set[int] = max(nx.connected_components(g), key=len) if g.number_of_nodes() else set()
    print(
        f"[graph] {g.number_of_nodes()} vertices, "
        f"{g.number_of_edges()} edges in {time.monotonic() - t0:.1f}s "
        f"(largest component: {len(biggest_component)} vertices)"
    )

    print("\n[routes] computing shortest paths...")
    successes = 0
    for spec in KTZ_ROUTES:
        name = spec["name"]
        start = spec["start"]
        end = spec["end"]
        slug = slugify(name)
        out_path = OUTPUT_DIR / f"{slug}.geojson"

        u = nearest_node(coord_by_node, *start, allowed=biggest_component)
        v = nearest_node(coord_by_node, *end, allowed=biggest_component)
        if u is None or v is None:
            print(f"  [skip] {name}: no nearby rail node")
            continue
        try:
            path = nx.dijkstra_path(g, u, v, weight="weight")
        except nx.NetworkXNoPath:
            print(f"  [skip] {name}: no path between endpoints")
            continue
        polyline = stitch_polyline(g, path)
        if not polyline:
            print(f"  [skip] {name}: empty polyline")
            continue

        before_pts = len(polyline)
        polyline = simplify(polyline)
        length_km = polyline_length_m(polyline) / 1000.0

        stations = attach_stations(polyline, handler.stations)

        write_geojson(
            name=name,
            electrified=spec["electrified"],
            polyline=polyline,
            stations=stations,
            out_path=out_path,
        )
        print(
            f"  [ok]   {name}: {before_pts} -> {len(polyline)} pts, "
            f"{length_km:.0f} km, {len(stations)} stations -> {out_path.relative_to(REPO_ROOT)}"
        )
        successes += 1

    print(f"\nWrote {successes}/{len(KTZ_ROUTES)} routes.")
    return 0 if successes == len(KTZ_ROUTES) else 1


if __name__ == "__main__":
    sys.exit(main())
