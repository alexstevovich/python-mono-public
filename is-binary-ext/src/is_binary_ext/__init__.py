import os
from pathlib import Path

__all__ = ["BINARY_EXTENSIONS", "is_binary_ext"]

BINARY_EXTENSIONS = frozenset(
    {
        ".avi",
        ".dll",
        ".exe",
        ".gif",
        ".gz",
        ".jpeg",
        ".jpg",
        ".mov",
        ".mp3",
        ".mp4",
        ".pdf",
        ".png",
        ".tar",
        ".ttf",
        ".webp",
        ".woff",
        ".woff2",
        ".zip",
    }
)


def is_binary_ext(file_path: str | os.PathLike[str]) -> bool:
    """Return whether a path has a recognized binary extension."""
    return Path(file_path).suffix.lower() in BINARY_EXTENSIONS
