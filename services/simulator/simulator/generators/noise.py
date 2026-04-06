import random


def add_noise(value: float, nominal: float) -> float:
    """Gaussian sensor noise (~0.5% of nominal) with rare EMI spikes."""
    value += random.gauss(0, nominal * 0.005) if nominal != 0 else random.gauss(0, 0.01)

    # Rare EMI spike, ~0.1% per tick.
    if random.random() < 0.001:
        value += random.gauss(0, nominal * 0.05) if nominal != 0 else random.gauss(0, 0.1)

    return value
