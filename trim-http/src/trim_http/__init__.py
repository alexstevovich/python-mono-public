__all__ = ["trim_http"]


def trim_http(value: str) -> str:
    """Remove a lowercase HTTP or HTTPS scheme prefix."""
    if not isinstance(value, str):
        raise TypeError("trim_http expects a string")
    if value.startswith("https://"):
        return value[8:]
    if value.startswith("http://"):
        return value[7:]
    return value
