__all__ = ["cardinal_power"]


def cardinal_power(cardinality: int, length: int) -> int:
    """Return the exact number of values in a fixed-length symbol space."""
    if isinstance(cardinality, bool) or not isinstance(cardinality, int):
        raise TypeError("cardinality must be a positive integer")
    if cardinality < 1:
        raise ValueError("cardinality must be a positive integer")
    if isinstance(length, bool) or not isinstance(length, int):
        raise TypeError("length must be a non-negative integer")
    if length < 0:
        raise ValueError("length must be a non-negative integer")
    return cardinality**length
