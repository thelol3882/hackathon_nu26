"""
EMA / Kalman pre-filter for raw sensor values.

Formula: x̂_k = K · z_k + (1 - K) · x̂_{k-1}

where K is the gain (0 < K ≤ 1):
  - Low K  (≈0.10) → heavy smoothing for slow thermal sensors (1 Hz)
  - High K (≈0.30) → light smoothing for fast electrodynamic sensors (50 Hz)

State is kept in-process. In production this should be Redis-backed so
multiple replicas share state, but for a single-instance demo in-process is
sufficient and avoids network round-trips on the hot path.
"""

from shared.constants import EMA_GAINS

# (locomotive_id_str, sensor_type_str) → last filtered value
_ema_state: dict[tuple[str, str], float] = {}


def ema_filter(locomotive_id: str, sensor_type: str, raw_value: float) -> float:
    """
    Apply an EMA filter to a single sensor reading.

    Returns the filtered value x̂_k.
    On first call for a given (locomotive_id, sensor_type) pair the raw value
    is returned as-is (cold start).
    """
    key = (locomotive_id, sensor_type)
    prev = _ema_state.get(key)

    if prev is None:
        # Cold start — seed the state with the first observation
        _ema_state[key] = raw_value
        return raw_value

    gain = EMA_GAINS.get(sensor_type, EMA_GAINS["__default__"])
    filtered = gain * raw_value + (1.0 - gain) * prev
    _ema_state[key] = filtered
    return filtered


def reset_filter(locomotive_id: str, sensor_type: str | None = None) -> None:
    """
    Clear EMA state for a locomotive (e.g. after reconnect / maintenance).
    If sensor_type is None, clears all sensors for that locomotive.
    """
    if sensor_type is not None:
        _ema_state.pop((locomotive_id, sensor_type), None)
    else:
        keys_to_delete = [k for k in _ema_state if k[0] == locomotive_id]
        for k in keys_to_delete:
            del _ema_state[k]
