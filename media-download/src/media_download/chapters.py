from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yt_dlp


def format_upload_date(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y%m%d").date().isoformat()
    except ValueError:
        return value


def make_chapter_metadata(
    info: dict[str, Any], source_extension: str
) -> list[dict[str, Any]]:
    chapters = info.get("chapters")
    if not isinstance(chapters, list):
        return []
    result: list[dict[str, Any]] = []
    for index, chapter in enumerate(chapters, start=1):
        if not isinstance(chapter, dict):
            continue
        title = chapter.get("title") or f"Chapter {index}"
        start_time = chapter.get("start_time")
        end_time = chapter.get("end_time")
        duration = (
            end_time - start_time
            if isinstance(start_time, (int, float))
            and isinstance(end_time, (int, float))
            else None
        )
        safe_title = yt_dlp.utils.sanitize_filename(
            str(title), restricted=False, is_id=False
        )
        result.append(
            {
                "index": index,
                "title": title,
                "start_seconds": start_time,
                "end_seconds": end_time,
                "duration_seconds": duration,
                "filename": f"{safe_title}.{source_extension}",
            }
        )
    return result


def download_audio_chapters(url: str, output_directory: Path) -> tuple[Path, Path]:
    """Download and split source audio into an explicitly selected directory."""
    output_directory = output_directory.expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    options = {
        "format": "bestaudio/best",
        "windowsfilenames": True,
        "noplaylist": True,
        "writethumbnail": True,
        "convertthumbnails": "jpg",
        "outtmpl": {
            "default": str(output_directory / "%(title)s" / "Full - %(title)s.%(ext)s"),
            "chapter": str(
                output_directory / "%(title)s" / "%(section_title)s.%(ext)s"
            ),
            "thumbnail": str(output_directory / "%(title)s" / "cover.%(ext)s"),
        },
        "postprocessors": [{"key": "FFmpegSplitChapters", "force_keyframes": True}],
        "keepvideo": True,
        "overwrites": False,
        "quiet": False,
        "no_warnings": False,
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True)
        if info is None:
            raise RuntimeError("yt-dlp did not return video information.")
        title = info.get("title")
        if not title:
            raise RuntimeError("The video does not have a readable title.")
        audio_path = Path(downloader.prepare_filename(info))
        media_directory = audio_path.parent
        extension = audio_path.suffix.lstrip(".") or str(info.get("ext") or "webm")
        metadata = {
            "title": title,
            "url": info.get("webpage_url") or url,
            "video_id": info.get("id"),
            "uploader": info.get("uploader"),
            "uploader_id": info.get("uploader_id"),
            "channel": info.get("channel"),
            "channel_id": info.get("channel_id"),
            "channel_url": info.get("channel_url"),
            "upload_date": format_upload_date(info.get("upload_date")),
            "duration_seconds": info.get("duration"),
            "description": info.get("description"),
            "thumbnail": "cover.jpg",
            "source_audio": {
                "filename": audio_path.name,
                "extension": extension,
                "format_id": info.get("format_id"),
                "audio_codec": info.get("acodec"),
                "audio_bitrate_kbps": info.get("abr"),
                "sample_rate_hz": info.get("asr"),
            },
            "chapters": make_chapter_metadata(info, extension),
        }
        metadata_path = media_directory / "metadata.json"
        with metadata_path.open("w", encoding="utf-8") as output:
            json.dump(metadata, output, ensure_ascii=False, indent=2)
    return media_directory, metadata_path
