import re
from typing import Any

__all__ = ["camel_to_snake_keys"]

_ACRONYM_BOUNDARY = re.compile(r"([A-Z]+)([A-Z][a-z])")
_CASE_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")


def _camel_to_snake(value: str) -> str:
    value = _ACRONYM_BOUNDARY.sub(r"\1_\2", value)
    return _CASE_BOUNDARY.sub(r"\1_\2", value).lower()


def camel_to_snake_keys(value: Any) -> Any:
    """Recursively transform string mapping keys without mutating the input."""
    if isinstance(value, dict):
        converted = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError("mapping keys must be strings")
            converted[_camel_to_snake(key)] = camel_to_snake_keys(child)
        return converted
    if isinstance(value, list):
        return [camel_to_snake_keys(child) for child in value]
    if isinstance(value, tuple):
        return tuple(camel_to_snake_keys(child) for child in value)
    return value
