"""Dry-run: generate a few ticks and print the telemetry JSON to stdout."""

import json
import random
from datetime import UTC, datetime

from shared.enums import LocomotiveType
from shared.schemas.telemetry import GPSCoordinate, TelemetryReading
from simulator.generators.kz8a import generate_kz8a
from simulator.generators.te33a import generate_te33a
from simulator.models.fleet import generate_fleet
from simulator.models.locomotive_state import get_gps, tick

FLEET_SIZE = 5
TICKS = 3
SEED = 42


def main() -> None:
    random.seed(SEED)
    fleet = generate_fleet(FLEET_SIZE)

    print(f"=== Fleet: {FLEET_SIZE} locomotives, {TICKS} ticks ===\n")

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
                gps=GPSCoordinate(latitude=lat, longitude=lon),
                sensors=sensors,
            )

            data = reading.model_dump(mode="json")
            print(f"\n[{loco.loco_type.value}] {loco.id} | mode={loco.mode.value} speed={loco.speed:.1f} km/h")
            print(f"  GPS: ({lat:.4f}, {lon:.4f})")
            print(f"  Sensors ({len(sensors)}):")
            for s in sensors:
                print(f"    {s.sensor_type.value:>25s} = {s.value:>10.2f} {s.unit}")

            # Also show the full JSON for one loco per tick
            if loco is fleet[0]:
                print(f"\n  Full JSON payload:\n{json.dumps(data, indent=2, default=str)}")

        print()


if __name__ == "__main__":
    main()
