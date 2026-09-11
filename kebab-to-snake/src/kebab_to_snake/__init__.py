__all__ = ["kebab_to_snake"]


def kebab_to_snake(value: str) -> str:
    """Replace every hyphen in *value* with an underscore."""
    if not isinstance(value, str):
        raise TypeError("kebab_to_snake expects a string")
    return value.replace("-", "_")
