"""
ABBEY smooth state update utilities.

NUMBA TARGET:
This file is intended to be made Numba-compatible later.
Keep functions numeric, simple, and free of object/dataclass dependencies.
"""


import math


def smooth_bounded_update(
    x: float,
    up: float,
    down: float,
    dt_hours: float,
) -> float:
    """
    Smooth bounded state update.

    x_next = x + dt * (up * (1 - x) - down * x)

    Assumes x is normally in [0, 1].
    No hard clipping is applied.
    """
    return x + dt_hours * (up * (1.0 - x) - down * x)


def smooth_pressure(raw: float, scale: float = 1.0) -> float:
    """
    Converts an arbitrary raw influence into a smooth positive pressure.

    Output is in (0, 1), using a sigmoid.
    """
    if scale <= 0:
        raise ValueError("scale must be positive.")

    z = raw / scale

    # Numerical safety for large values
    if z >= 60:
        return 1.0
    if z <= -60:
        return 0.0

    return 1.0 / (1.0 + math.exp(-z))


def smooth_signed_pressure(raw: float, scale: float = 1.0) -> float:
    """
    Converts raw influence into a smooth signed pressure in (-1, 1).

    Useful when we want positive and negative influence in one value.
    """
    if scale <= 0:
        raise ValueError("scale must be positive.")

    return math.tanh(raw / scale)