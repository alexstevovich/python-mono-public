import math

__all__ = ["reduce_fraction"]


def reduce_fraction(numerator: int, denominator: int) -> str:
    """Return an integer fraction in lowest terms with a normalized sign."""
    if isinstance(numerator, bool) or not isinstance(numerator, int):
        raise TypeError("numerator must be an integer")
    if isinstance(denominator, bool) or not isinstance(denominator, int):
        raise TypeError("denominator must be an integer")
    if denominator == 0:
        raise ValueError("denominator must not be zero")
    divisor = math.gcd(numerator, denominator)
    reduced_numerator = numerator // divisor
    reduced_denominator = denominator // divisor
    if reduced_denominator < 0:
        reduced_numerator *= -1
        reduced_denominator *= -1
    return f"{reduced_numerator}/{reduced_denominator}"
