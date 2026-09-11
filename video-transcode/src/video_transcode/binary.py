from __future__ import annotations

import shutil
from dataclasses import dataclass

from .errors import BinaryNotFoundError


@dataclass(frozen=True)
class MediaTools:
    ffmpeg: str
    ffprobe: str


def find_media_tools() -> MediaTools:
    """Locate the separately installed FFmpeg tools through PATH."""
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    missing = [
        name
        for name, path in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe))
        if path is None
    ]
    if missing:
        names = " and ".join(missing)
        raise BinaryNotFoundError(
            f"{names} not found on PATH; install FFmpeg system-wide and ensure both ffmpeg and ffprobe are available"
        )
    return MediaTools(ffmpeg=ffmpeg, ffprobe=ffprobe)
