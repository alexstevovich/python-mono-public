from __future__ import annotations

from pathlib import Path

import yt_dlp


def download_audio(
    url: str,
    output_directory: Path,
    *,
    download_playlist: bool = False,
) -> None:
    """Download the highest-quality source audio to an explicit directory."""
    output_directory = output_directory.expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    options = {
        "format": "bestaudio/best",
        "outtmpl": str(output_directory / "%(title)s [%(id)s].%(ext)s"),
        "noplaylist": not download_playlist,
        "ignoreerrors": download_playlist,
        "overwrites": False,
        "quiet": False,
        "no_warnings": False,
        "windowsfilenames": True,
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        result = downloader.download([url])
    if result != 0:
        raise RuntimeError("yt-dlp reported that the download failed.")
