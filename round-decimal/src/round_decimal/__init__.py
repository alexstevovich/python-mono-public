import math
from decimal import ROUND_HALF_UP, Decimal

__all__ = ["round_decimal"]


def round_decimal(value: float, places: int = 0) -> float:
    """Round a finite number using decimal half-up semantics."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("value must be a finite number")
    if not math.isfinite(value):
        raise ValueError("value must be a finite number")
    if isinstance(places, bool) or not isinstance(places, int):
        raise TypeError("places must be an integer")
    quantum = Decimal(1).scaleb(-places)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))
