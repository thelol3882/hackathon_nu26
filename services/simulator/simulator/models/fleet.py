from __future__ import annotations

import random
import uuid

from shared.enums import LocomotiveType
from shared.utils import generate_id
from simulator.models.locomotive_state import (
    LocomotiveMode,
    LocomotiveState,
    Route,
)

# Real Kazakhstan railway routes
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

_ELECTRIFIED_ROUTES = [r for r in ROUTES if r.electrified]
_NON_ELECTRIFIED_ROUTES = [r for r in ROUTES if not r.electrified]

_INITIAL_MODES = [
    LocomotiveMode.DEPOT,
    LocomotiveMode.DEPARTURE,
    LocomotiveMode.CRUISING,
    LocomotiveMode.CRUISING,
    LocomotiveMode.CRUISING,
    LocomotiveMode.ARRIVAL,
]


def generate_fleet(n: int = 1700) -> list[LocomotiveState]:
    te33a_count = int(n * 0.6)
    locos: list[LocomotiveState] = []

    for i in range(n):
        loco_type = LocomotiveType.TE33A if i < te33a_count else LocomotiveType.KZ8A

        if loco_type == LocomotiveType.KZ8A:
            route = random.choice(_ELECTRIFIED_ROUTES)
        else:
            route = random.choice(ROUTES)  # TE33A can run on any route

        mode = random.choice(_INITIAL_MODES)
        speed = 0.0
        notch = 0
        if mode == LocomotiveMode.CRUISING:
            speed = random.uniform(60.0, 100.0)
            notch = random.randint(5, 7) if loco_type == LocomotiveType.TE33A else 0
        elif mode == LocomotiveMode.DEPARTURE:
            speed = random.uniform(10.0, 40.0)
            notch = random.randint(1, 3) if loco_type == LocomotiveType.TE33A else 0
        elif mode == LocomotiveMode.ARRIVAL:
            speed = random.uniform(10.0, 40.0)
            notch = random.randint(0, 2) if loco_type == LocomotiveType.TE33A else 0

        locos.append(
            LocomotiveState(
                id=uuid.UUID(str(generate_id())),
                loco_type=loco_type,
                route=route,
                mode=mode,
                route_progress=random.random(),
                speed=speed,
                notch=notch,
                fuel_level=random.uniform(30.0, 95.0),
                coolant_temp=72.0 + random.uniform(0, 10),
                traction_motor_temp=40.0 + random.uniform(0, 20),
                igbt_temp=35.0 + random.uniform(0, 15),
                transformer_temp=45.0 + random.uniform(0, 10),
            )
        )

    return locos
