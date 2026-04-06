# Roadmap

Future improvements that are nice to have but not blocking the current iteration.

## Map / route geometry

- **Replace synthetic polylines with real OSM railway data.**
  Today the route polylines in `shared/shared/route_geometry.py` are
  generated as smoothed random walks between two endpoints. They look
  hand-drawn but they don't follow real KTZ tracks. Switch to either:
  - the OpenStreetMap Overpass API (`way[railway=rail]` filter), pulled
    once and cached as GeoJSON in `shared/data/routes/`, or
  - GTFS feed if Kazakhstan Temir Zholy publishes one.

- **Replace synthetic stations with real KTZ station list.**
  Same iteration as the OSM import — once we have real polylines we can
  also pin real stations to them, with proper Russian/Kazakh names instead
  of `Разъезд X км` placeholders.

- **Per-locomotive route in replay mode.**
  `RouteMap` currently passes `routeName={null}` for replay because
  historical snapshots don't carry it. Add a small locomotive metadata
  endpoint or stash the route on the locomotive record so the replay
  view can render the polyline too.

## Telemetry / charts

- **Incremental tail fetch for TrendsPanel.**
  Today the panel re-fetches the full visible window on every poll.
  DigitalOcean instead pulls only `[lastKnownTs, now]` and appends to
  a local buffer. With server-side LTTB this is non-trivial — see the
  notes I left in chat — but it would cut traffic by ~99% on long
  windows. Worth doing if real-world traffic ever becomes a concern.
