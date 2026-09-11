from __future__ import annotations

import argparse
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import yt_dlp

from .audio import download_audio
from .chapters import download_audio_chapters
from .video import download_video


def default_downloads_directory() -> Path:
    return Path.home() / "Downloads"


def _require_ffmpeg(reason: str) -> bool:
    if shutil.which("ffmpeg") is not None:
        return True
    print(f"Error: FFmpeg is required {reason}.", file=sys.stderr)
    return False


def _run(operation: Callable[[], None]) -> int:
    try:
        operation()
        return 0
    except yt_dlp.utils.DownloadError as error:
        print(f"\nDownload failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nDownload cancelled.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"\nUnexpected error: {error}", file=sys.stderr)
        return 1


def audio_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="download-audio", description="Download the best source audio."
    )
    parser.add_argument("url")
    parser.add_argument(
        "-o", "--output", type=Path, default=default_downloads_directory()
    )
    parser.add_argument("--playlist", action="store_true")
    return parser


def audio_main(argv: list[str] | None = None) -> int:
    arguments = audio_parser().parse_args(argv)
    return _run(
        lambda: download_audio(
            arguments.url,
            arguments.output,
            download_playlist=arguments.playlist,
        )
    )


def chapters_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="download-audio-chapters",
        description="Download audio and split it by chapters.",
    )
    parser.add_argument("url")
    parser.add_argument(
        "-o", "--output", type=Path, default=default_downloads_directory()
    )
    return parser


def chapters_main(argv: list[str] | None = None) -> int:
    arguments = chapters_parser().parse_args(argv)
    if not _require_ffmpeg("to split chapters and convert thumbnails"):
        return 1

    def operation() -> None:
        directory, metadata = download_audio_chapters(arguments.url, arguments.output)
        print(
            f"\nDownload complete.\nSaved in: {directory}\nMetadata saved to: {metadata}"
        )

    return _run(operation)


def video_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="download-video",
        description="Download the best available video and audio.",
    )
    parser.add_argument("url")
    parser.add_argument(
        "-o", "--output", type=Path, default=default_downloads_directory()
    )
    return parser


def video_main(argv: list[str] | None = None) -> int:
    arguments = video_parser().parse_args(argv)
    if not _require_ffmpeg("to merge video and audio streams"):
        return 1

    def operation() -> None:
        path = download_video(arguments.url, arguments.output)
        print(f"\nDownload complete.\nSaved in: {path.parent}\nFilename: {path.name}")

    return _run(operation)
