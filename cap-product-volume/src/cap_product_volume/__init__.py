import math
from collections.abc import Iterable

__all__ = ["cap_product_volume"]


def cap_product_volume(
    dimensions: Iterable[float], maximum_volume: float
) -> list[float]:
    """Scale dimensions uniformly when their product exceeds the maximum."""
    values = list(dimensions)
    if not values:
        raise ValueError("dimensions must be non-empty")
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("dimensions must contain non-negative finite numbers")
    if not math.isfinite(maximum_volume) or maximum_volume <= 0:
        raise ValueError("maximum_volume must be a positive finite number")
    volume = math.prod(values)
    if volume <= maximum_volume:
        return values
    scale = (maximum_volume / volume) ** (1 / len(values))
    return [value * scale for value in values]
