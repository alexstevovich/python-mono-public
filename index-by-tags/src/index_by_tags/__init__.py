from collections.abc import Callable, Hashable, Iterable, Mapping
from typing import Any, TypeVar

__all__ = ["index_by_tags"]

Item = TypeVar("Item", bound=Mapping[str, Any])


def _mapping_tags(item: Item) -> Iterable[Hashable] | None:
    return item["tags"]


def index_by_tags(
    items: Iterable[Item],
    get_tags: Callable[[Item], Iterable[Hashable] | None] | None = None,
) -> dict[Hashable, list[Item]]:
    """Index each mapping under every one of its tags."""
    if get_tags is None:
        get_tags = _mapping_tags
    result: dict[Hashable, list[Item]] = {}
    for item in items:
        for tag in get_tags(item) or ():
            result.setdefault(tag, []).append(item)
    return result
