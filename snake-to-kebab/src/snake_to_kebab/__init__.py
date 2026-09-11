__all__ = ["snake_to_kebab"]


def snake_to_kebab(value: str) -> str:
    """Replace every underscore in *value* with a hyphen."""
    if not isinstance(value, str):
        raise TypeError("snake_to_kebab expects a string")
    return value.replace("_", "-")
