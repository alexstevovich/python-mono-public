import re
from typing import Any

__all__ = ["snake_to_camel_keys"]

_SNAKE_BOUNDARY = re.compile(r"_([a-z])")


def _snake_to_camel(value: str) -> str:
    return _SNAKE_BOUNDARY.sub(lambda match: match.group(1).upper(), value)


def snake_to_camel_keys(value: Any) -> Any:
    """Recursively transform string mapping keys without mutating the input."""
    if isinstance(value, dict):
        converted = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError("mapping keys must be strings")
            converted[_snake_to_camel(key)] = snake_to_camel_keys(child)
        return converted
    if isinstance(value, list):
        return [snake_to_camel_keys(child) for child in value]
    if isinstance(value, tuple):
        return tuple(snake_to_camel_keys(child) for child in value)
    return value
