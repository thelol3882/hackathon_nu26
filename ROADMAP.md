# Roadmap

Future improvements that are nice to have but not blocking the current iteration.

## Map / route geometry

- **Refresh the OSM dataset periodically.** The committed GeoJSON
  routes under `shared/data/routes/` were generated against a single
  snapshot of the Geofabrik Kazakhstan PBF. Re-run
  `tools/import_osm_railways.py` (after `uv sync --group osm`)
  every few months to pick up newly mapped tracks and station
  renames. The script is idempotent and the diff is reviewable.

- **Per-locomotive route in replay mode.**
  `RouteMap` currently passes `routeName={null}` for replay because
  historical snapshots don't carry it. Add a small locomotive metadata
  endpoint or stash the route on the locomotive record so the replay
  view can render the polyline too.

- **Locomotive icon orientation along bearing.** We already publish
  `gps.bearing_deg` from the simulator and store it in the telemetry
  slice — the marker just doesn't rotate yet. A quick `transform:
  rotate(...)` on the divIcon's inner div would make the train point
  the right way.

## Telemetry / charts

- **Incremental tail fetch for TrendsPanel.**
  Today the panel re-fetches the full visible window on every poll.
  DigitalOcean instead pulls only `[lastKnownTs, now]` and appends to
  a local buffer. With server-side LTTB this is non-trivial — see the
  notes in chat about the LTTB-on-tail trap and the recommended
  "raw bucketed buffer + client-side LTTB" architecture — but it
  would cut trends traffic by ~99% on long windows. Worth doing if
  real-world traffic ever becomes a concern.
