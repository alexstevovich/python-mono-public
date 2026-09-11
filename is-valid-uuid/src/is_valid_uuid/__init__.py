import re

__all__ = ["is_valid_uuid"]

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_LOWERCASE_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def is_valid_uuid(
    value: object, *, version: int | None = None, strict_case: bool = False
) -> bool:
    """Return whether *value* is a canonical RFC 9562 UUID string."""
    if not isinstance(value, str):
        return False
    if version is not None and (
        isinstance(version, bool)
        or not isinstance(version, int)
        or not 1 <= version <= 8
    ):
        return False
    pattern = _LOWERCASE_UUID_PATTERN if strict_case else _UUID_PATTERN
    if pattern.fullmatch(value) is None:
        return False
    return version is None or int(value[14]) == version
