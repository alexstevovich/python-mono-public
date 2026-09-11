from __future__ import annotations

from pathlib import Path

from .errors import ValidationError
from .models import (
    AudioCodec,
    AudioOptions,
    AverageBitrate,
    Container,
    OutputOptions,
    SubtitleMode,
    SubtitleOptions,
    SubtitleSelection,
    VideoCodec,
    VideoOptions,
)

EXTENSIONS = {
    ".mkv": Container.MKV,
    ".webm": Container.WEBM,
    ".mp4": Container.MP4,
    ".mov": Container.MOV,
}


def resolve_container(path: str | Path, explicit: Container | None = None) -> Container:
    if explicit:
        return explicit
    try:
        return EXTENSIONS[Path(path).suffix.lower()]
    except KeyError as exc:
        raise ValidationError(
            "cannot infer container; use .mkv, .webm, .mp4, .mov, or --container"
        ) from exc


def validate_options(
    video: VideoOptions,
    audio: AudioOptions,
    subtitles: SubtitleOptions,
    output: OutputOptions,
    output_path: str | Path,
) -> Container:
    container = resolve_container(output_path, output.container)
    if (
        isinstance(video.rate_control, AverageBitrate)
        and video.rate_control.passes == 2
    ):
        raise ValidationError(
            "two-pass execution is not implemented; use --video-passes 1"
        )
    if video.codec == VideoCodec.AV1_NVENC and video.bit_depth == 10:
        pass
    if container == Container.WEBM:
        if video.codec not in (VideoCodec.SVT_AV1, VideoCodec.AV1_NVENC):
            raise ValidationError("WebM output requires AV1 in this version")
        if audio.codec not in (AudioCodec.OPUS, AudioCodec.COPY):
            raise ValidationError("WebM audio must be Opus or compatible passthrough")
        if (
            subtitles.tracks != SubtitleSelection.NONE
            and subtitles.mode == SubtitleMode.COPY
        ):
            raise ValidationError(
                "subtitle copy to WebM cannot be validated safely; select convert or none"
            )
    if (
        container in (Container.MP4, Container.MOV)
        and subtitles.tracks != SubtitleSelection.NONE
        and subtitles.mode == SubtitleMode.COPY
    ):
        raise ValidationError(
            f"subtitle copy to {container.value} is not reliably interoperable; use --subtitle-mode convert"
        )
    if (
        subtitles.mode == SubtitleMode.BURN
        and subtitles.tracks == SubtitleSelection.ALL
    ):
        raise ValidationError(
            "burn mode supports first or forced subtitle selection, not all"
        )
    if audio.codec == AudioCodec.COPY and (
        audio.bitrate is not None
        or audio.channels != "source"
        or audio.sample_rate != "source"
    ):
        raise ValidationError(
            "audio bitrate, channel, and sample-rate changes require an encoded audio codec, not copy"
        )
    return container
