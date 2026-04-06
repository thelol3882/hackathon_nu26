"""Dry-run: spin up a few locomotives by hand and print their telemetry.

Useful for inspecting sensor outputs without bringing up the whole
docker stack. Mirrors what the operator would do via the dashboard,
just from a Python script.
"""

import json
import random
import uuid
from datetime import UTC, datetime

from shared.enums import LocomotiveType
from shared.route_geometry import ROUTES
from shared.schemas.telemetry import GPSCoordinate, TelemetryReading
from simulator.generators.kz8a import generate_kz8a
from simulator.generators.te33a import generate_te33a
from simulator.models.locomotive_state import (
    LocomotiveMode,
    LocomotiveScenario,
    LocomotiveState,
    get_gps,
    tick,
)

TICKS = 3
SEED = 42


def main() -> None:
    random.seed(SEED)

    # Hand-built tiny fleet — one of each type, two scenarios so the
    # generators get exercised.
    fleet: list[LocomotiveState] = [
        LocomotiveState(
            id=uuid.uuid4(),
            loco_type=LocomotiveType.TE33A,
            route=ROUTES[0],  # Almaty-Astana
            name="TE33A demo",
            mode=LocomotiveMode.CRUISING,
            scenario=LocomotiveScenario.NORMAL,
            auto_mode=True,
            speed=80.0,
        ),
        LocomotiveState(
            id=uuid.uuid4(),
            loco_type=LocomotiveType.KZ8A,
            route=ROUTES[3],  # Almaty-Shymkent
            name="KZ8A demo",
            mode=LocomotiveMode.CRUISING,
            scenario=LocomotiveScenario.DEGRADATION,
            auto_mode=True,
            speed=90.0,
        ),
    ]

    print(f"=== Fleet: {len(fleet)} locomotives, {TICKS} ticks ===\n")

    for t in range(TICKS):
        print(f"--- Tick {t + 1} ---")
        for loco in fleet:
            tick(loco)
            sensors = generate_te33a(loco) if loco.loco_type == LocomotiveType.TE33A else generate_kz8a(loco)
            lat, lon = get_gps(loco)

            reading = TelemetryReading(
                locomotive_id=loco.id,
                locomotive_type=loco.loco_type,
                timestamp=datetime.now(UTC),
                sample_rate_hz=1.0,
                gps=GPSCoordinate(latitude=lat, longitude=lon, bearing_deg=loco.bearing_deg),
                sensors=sensors,
                route_name=loco.route.name,
            )

            data = reading.model_dump(mode="json")
            print(
                f"\n[{loco.loco_type.value}] {loco.id} | "
                f"mode={loco.mode.value} scenario={loco.scenario.value} speed={loco.speed:.1f} km/h"
            )
            print(f"  Route: {loco.route.name} ({loco.segment_progress * 100:.1f}%)")
            print(f"  GPS: ({lat:.4f}, {lon:.4f})  bearing={loco.bearing_deg:.0f}°")
            print(f"  Sensors ({len(sensors)}):")
            for s in sensors:
                print(f"    {s.sensor_type.value:>25s} = {s.value:>10.2f} {s.unit}")

            if loco is fleet[0]:
                print(f"\n  Full JSON payload:\n{json.dumps(data, indent=2, default=str)}")

        print()


if __name__ == "__main__":
    main()
