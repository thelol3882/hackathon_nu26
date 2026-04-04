"""
EMA pre-filter: x̂_k = K · z_k + (1 - K) · x̂_{k-1}

K per sensor type (see EMA_GAINS): ~0.10 for slow thermal, ~0.30 for fast electrodynamic.
State is in-process; for multi-replica deployments it should be Redis-backed.
"""

from shared.constants import EMA_GAINS

# (locomotive_id_str, sensor_type_str) → last filtered value
_ema_state: dict[tuple[str, str], float] = {}


def ema_filter(locomotive_id: str, sensor_type: str, raw_value: float) -> float:
    """Returns filtered x̂_k. On cold start returns raw_value unchanged."""
    key = (locomotive_id, sensor_type)
    prev = _ema_state.get(key)

    if prev is None:
        _ema_state[key] = raw_value
        return raw_value

    gain = EMA_GAINS.get(sensor_type, EMA_GAINS["__default__"])
    filtered = gain * raw_value + (1.0 - gain) * prev
    _ema_state[key] = filtered
    return filtered


def reset_filter(locomotive_id: str, sensor_type: str | None = None) -> None:
    """Clear EMA state for a locomotive (e.g. after reconnect). None clears all sensors."""
    if sensor_type is not None:
        _ema_state.pop((locomotive_id, sensor_type), None)
    else:
        keys_to_delete = [k for k in _ema_state if k[0] == locomotive_id]
        for k in keys_to_delete:
            del _ema_state[k]
