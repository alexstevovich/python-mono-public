from __future__ import annotations

from pathlib import Path
from typing import Any

import yt_dlp


def has_video_stream(info: dict[str, Any]) -> bool:
    requested_formats = info.get("requested_formats")
    if isinstance(requested_formats, list):
        return any(
            isinstance(media_format, dict)
            and media_format.get("vcodec") not in (None, "none")
            for media_format in requested_formats
        )
    return info.get("vcodec") not in (None, "none")


def download_video(url: str, output_directory: Path) -> Path:
    """Download the highest-quality available video to an explicit directory."""
    output_directory = output_directory.expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    options = {
        "format": (
            "bestvideo[vcodec!=none]+bestaudio[acodec!=none]"
            "/best[vcodec!=none][acodec!=none]"
        ),
        "outtmpl": str(output_directory / "%(title)s [%(id)s].%(ext)s"),
        "noplaylist": True,
        "windowsfilenames": True,
        "overwrites": False,
        "quiet": False,
        "no_warnings": False,
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True)
        if info is None:
            raise RuntimeError("yt-dlp did not return video information.")
        if not has_video_stream(info):
            raise RuntimeError("The selected download contains no video stream.")
        return Path(downloader.prepare_filename(info))
