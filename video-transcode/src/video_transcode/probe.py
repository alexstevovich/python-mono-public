from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .errors import BinaryNotFoundError, ProbeError
from .models import ChapterInfo, MediaInfo, StreamInfo


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_probe(data: dict[str, Any], path: str | Path) -> MediaInfo:
    streams = []
    for raw in data.get("streams", []):
        tags = raw.get("tags", {})
        streams.append(
            StreamInfo(
                index=int(raw["index"]),
                codec_type=raw.get("codec_type", "unknown"),
                codec_name=raw.get("codec_name"),
                width=_int(raw.get("width")),
                height=_int(raw.get("height")),
                pixel_format=raw.get("pix_fmt"),
                bit_depth=_int(raw.get("bits_per_raw_sample")),
                avg_frame_rate=raw.get("avg_frame_rate"),
                real_frame_rate=raw.get("r_frame_rate"),
                time_base=raw.get("time_base"),
                sample_aspect_ratio=raw.get("sample_aspect_ratio"),
                display_aspect_ratio=raw.get("display_aspect_ratio"),
                color_range=raw.get("color_range"),
                color_space=raw.get("color_space"),
                color_primaries=raw.get("color_primaries"),
                color_transfer=raw.get("color_transfer"),
                channels=_int(raw.get("channels")),
                channel_layout=raw.get("channel_layout"),
                sample_rate=_int(raw.get("sample_rate")),
                bit_rate=_int(raw.get("bit_rate")),
                language=tags.get("language"),
                title=tags.get("title"),
                disposition=dict(raw.get("disposition", {})),
                side_data=tuple(raw.get("side_data_list", [])),
                field_order=raw.get("field_order"),
            )
        )
    chapters = tuple(
        ChapterInfo(
            id=int(c.get("id", i)),
            start=float(c.get("start_time", 0)),
            end=float(c.get("end_time", 0)),
            tags=dict(c.get("tags", {})),
        )
        for i, c in enumerate(data.get("chapters", []))
    )
    fmt = data.get("format", {})
    return MediaInfo(
        Path(path),
        tuple(x for x in fmt.get("format_name", "").split(",") if x),
        _float(fmt.get("duration")),
        _int(fmt.get("bit_rate")),
        dict(fmt.get("tags", {})),
        tuple(streams),
        chapters,
    )


def probe_media(path: str | Path, ffprobe: str = "ffprobe") -> MediaInfo:
    binary = shutil.which(ffprobe)
    if not binary:
        raise BinaryNotFoundError(
            "ffprobe was not found on PATH; install FFmpeg and ensure ffprobe is available"
        )
    command = [
        binary,
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-show_chapters",
        "-of",
        "json",
        str(path),
    ]
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    if proc.returncode:
        raise ProbeError(f"ffprobe failed for {path}: {proc.stderr.strip()}")
    try:
        return parse_probe(json.loads(proc.stdout), path)
    except (ValueError, KeyError, TypeError) as exc:
        raise ProbeError(f"could not parse ffprobe output for {path}: {exc}") from exc
