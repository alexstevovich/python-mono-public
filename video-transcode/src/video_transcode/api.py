from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .binary import find_media_tools
from .builder import build_transcode_job
from .cropping import analyze_crop
from .errors import ValidationError
from .executor import execute_job
from .models import (
    AudioOptions,
    OutputOptions,
    ProgressEvent,
    SubtitleOptions,
    TranscodeResult,
    VideoOptions,
)
from .probe import probe_media


def transcode(
    input_path: str | Path,
    output_path: str | Path,
    *,
    video: VideoOptions | None = None,
    audio: AudioOptions | None = None,
    subtitles: SubtitleOptions | None = None,
    output: OutputOptions | None = None,
    progress_callback: Callable[[ProgressEvent], None] | None = None,
) -> TranscodeResult:
    tools = find_media_tools()
    output_options = output or OutputOptions()
    target = Path(output_path)
    if target.exists() and not output_options.overwrite:
        raise ValidationError(
            f"output already exists: {target}; pass overwrite=True to replace it"
        )
    media = probe_media(input_path, ffprobe=tools.ffprobe)
    video_options = video or VideoOptions()
    crop_analysis = (
        analyze_crop(input_path, media, ffmpeg=tools.ffmpeg)
        if video_options.crop == "auto"
        else None
    )
    job = build_transcode_job(
        input_path,
        output_path,
        media=media,
        video=video_options,
        audio=audio,
        subtitles=subtitles,
        output=output_options,
        ffmpeg=tools.ffmpeg,
        require_binary=True,
        progress=progress_callback is not None,
        crop_analysis=crop_analysis,
    )
    return execute_job(
        job, duration=media.duration, progress_callback=progress_callback
    )
