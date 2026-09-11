import os

__all__ = ["is_file_binary"]

_TEXT_CONTROL_BYTES = frozenset({8, 9, 10, 12, 13, 27})


def is_file_binary(
    file_path: str | os.PathLike[str], *, sample_size: int = 8192
) -> bool:
    """Return whether an initial byte sample appears to contain binary data."""
    if isinstance(sample_size, bool) or not isinstance(sample_size, int):
        raise TypeError("sample_size must be an integer")
    if sample_size < 1:
        raise ValueError("sample_size must be positive")
    with open(file_path, "rb") as file:
        sample = file.read(sample_size)
    if not sample:
        return False
    if b"\x00" in sample:
        return True
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        controls = sum(byte < 32 and byte not in _TEXT_CONTROL_BYTES for byte in sample)
        return controls / len(sample) > 0.30
    return False
