"""In-process EMA pre-filter for raw sensor values.

x̂_k = K·z_k + (1−K)·x̂_{k−1}. Per-sensor gain picked by EMA_GAINS; state is
in-process (single replica). Move to Redis if horizontal scaling is needed.
"""

from shared.constants import EMA_GAINS

_ema_state: dict[tuple[str, str], float] = {}


def ema_filter(locomotive_id: str, sensor_type: str, raw_value: float) -> float:
    """Filter one reading; cold-start returns the raw value unchanged."""
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
    """Clear EMA state for a locomotive; None sensor_type clears all sensors."""
    if sensor_type is not None:
        _ema_state.pop((locomotive_id, sensor_type), None)
    else:
        keys_to_delete = [k for k in _ema_state if k[0] == locomotive_id]
        for k in keys_to_delete:
            del _ema_state[k]
