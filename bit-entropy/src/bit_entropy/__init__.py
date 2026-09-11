import math

__all__ = ["bit_entropy"]


def bit_entropy(cardinality: int, length: int) -> float:
    """Return the entropy of a fixed-length symbol space in bits."""
    if isinstance(cardinality, bool) or not isinstance(cardinality, int):
        raise TypeError("cardinality must be a positive integer")
    if cardinality < 1:
        raise ValueError("cardinality must be a positive integer")
    if isinstance(length, bool) or not isinstance(length, int):
        raise TypeError("length must be a non-negative integer")
    if length < 0:
        raise ValueError("length must be a non-negative integer")
    return length * math.log2(cardinality)
