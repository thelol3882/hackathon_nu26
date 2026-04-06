from __future__ import annotations

import random
import uuid

import httpx

from shared.enums import LocomotiveType
from shared.observability import get_logger
from shared.route_geometry import ROUTES
from shared.utils import generate_id
from simulator.models.locomotive_state import (
    LocomotiveMode,
    LocomotiveState,
)

logger = get_logger(__name__)

# Routes are owned by the shared `route_geometry` module so the
# simulator and api-gateway agree on the same polyline + station data
# without one importing the other. ROUTES is re-exported here for
# legacy callers.
__all__ = ["ROUTES", "generate_fleet"]

_ELECTRIFIED_ROUTES = [r for r in ROUTES if r.electrified]

_INITIAL_MODES = [
    LocomotiveMode.DEPOT,
    LocomotiveMode.DEPARTURE,
    LocomotiveMode.CRUISING,
    LocomotiveMode.CRUISING,
    LocomotiveMode.CRUISING,
    LocomotiveMode.ARRIVAL,
]


def _fetch_locomotive_ids(gateway_url: str) -> list[dict] | None:
    """Fetch locomotive records from api-gateway. Returns list of {id, model} or None on failure."""
    try:
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            # Login as admin
            resp = client.post(
                f"{gateway_url}/auth/login",
                json={"username": "admin", "password": "admin"},
            )
            if resp.status_code != 200:
                logger.warning("Gateway login failed: %s", resp.status_code)
                return None
            token = resp.json()["access_token"]

            # Fetch all locomotive IDs via dedicated fleet endpoint
            resp = client.get(
                f"{gateway_url}/locomotives/fleet",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code != 200:
                logger.warning("Fetch fleet failed: %s", resp.status_code)
                return None
            return resp.json()
    except Exception:
        logger.warning("Could not reach gateway at %s, generating random fleet", gateway_url)
        return None


def generate_fleet(n: int = 1700, gateway_url: str | None = None) -> list[LocomotiveState]:
    gateway_locos = _fetch_locomotive_ids(gateway_url) if gateway_url else None

    if gateway_locos:
        te33a_ids = [rec for rec in gateway_locos if "TE33A" in rec.get("model", "")]
        kz8a_ids = [rec for rec in gateway_locos if "KZ8A" in rec.get("model", "")]
        logger.info(
            "Fetched %d locomotives from gateway (TE33A=%d, KZ8A=%d)",
            len(gateway_locos),
            len(te33a_ids),
            len(kz8a_ids),
        )
    else:
        te33a_ids = []
        kz8a_ids = []

    te33a_count = int(n * 0.6)
    locos: list[LocomotiveState] = []

    for i in range(n):
        loco_type = LocomotiveType.TE33A if i < te33a_count else LocomotiveType.KZ8A

        if loco_type == LocomotiveType.TE33A and te33a_ids:
            idx = i % len(te33a_ids)
            loco_id = uuid.UUID(te33a_ids[idx]["id"])
        elif loco_type == LocomotiveType.KZ8A and kz8a_ids:
            idx = (i - te33a_count) % len(kz8a_ids)
            loco_id = uuid.UUID(kz8a_ids[idx]["id"])
        else:
            loco_id = uuid.UUID(str(generate_id()))

        if loco_type == LocomotiveType.KZ8A:
            route = random.choice(_ELECTRIFIED_ROUTES)
        else:
            route = random.choice(ROUTES)

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

        # Random initial position along the polyline so the fleet is
        # already spread out at boot, instead of every locomotive
        # starting at the route origin and bunching up visually.
        initial_distance = random.uniform(0.0, route.length_m)
        locos.append(
            LocomotiveState(
                id=loco_id,
                loco_type=loco_type,
                route=route,
                mode=mode,
                distance_m=initial_distance,
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
