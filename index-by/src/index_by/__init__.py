from collections.abc import Hashable, Iterable, Mapping
from typing import Any, TypeVar

__all__ = ["index_by"]

Item = TypeVar("Item", bound=Mapping[str, Any])


def index_by(items: Iterable[Item], key: str) -> dict[Hashable, Item]:
    """Index mappings by *key*, retaining the final duplicate."""
    result: dict[Hashable, Item] = {}
    for item in items:
        index = item[key]
        if not isinstance(index, Hashable):
            raise TypeError("index values must be hashable")
        result[index] = item
    return result
