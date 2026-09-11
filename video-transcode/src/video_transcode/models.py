from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class VideoCodec(StrEnum):
    SVT_AV1 = "svt-av1"
    AV1_NVENC = "av1-nvenc"
    H264 = "h264"
    H265 = "h265"


class AudioCodec(StrEnum):
    COPY = "copy"
    OPUS = "opus"
    AAC = "aac"


class Selection(StrEnum):
    NONE = "none"
    FIRST = "first"
    ALL = "all"


class SubtitleSelection(StrEnum):
    NONE = "none"
    FIRST = "first"
    ALL = "all"
    FORCED = "forced"


class SubtitleMode(StrEnum):
    COPY = "copy"
    BURN = "burn"
    CONVERT = "convert"


class Container(StrEnum):
    MKV = "mkv"
    WEBM = "webm"
    MP4 = "mp4"
    MOV = "mov"


class ResolutionLimit(StrEnum):
    NONE = "none"
    SD_480 = "480p"
    HD_720 = "720p"
    HD_1080 = "1080p"
    QHD_1440 = "1440p"
    UHD_2160 = "2160p"


@dataclass(frozen=True)
class CropRect:
    width: int
    height: int
    x: int
    y: int

    def margins(
        self, source_width: int, source_height: int
    ) -> tuple[int, int, int, int]:
        return (
            self.y,
            source_height - self.y - self.height,
            self.x,
            source_width - self.x - self.width,
        )


@dataclass(frozen=True)
class CropAnalysis:
    crop: CropRect | None
    conclusive: bool
    samples_requested: int
    samples_succeeded: int
    candidates: tuple[CropRect, ...] = ()


@dataclass(frozen=True)
class ConstantQuality:
    value: float

    def __post_init__(self) -> None:
        if not 0 <= self.value <= 63:
            raise ValueError("constant quality must be between 0 and 63")


@dataclass(frozen=True)
class AverageBitrate:
    bitrate: int
    passes: int = 1

    def __post_init__(self) -> None:
        if self.bitrate <= 0:
            raise ValueError("bitrate must be positive")
        if self.passes not in (1, 2):
            raise ValueError("passes must be 1 or 2")


RateControl = ConstantQuality | AverageBitrate


@dataclass(frozen=True)
class VideoOptions:
    codec: VideoCodec = VideoCodec.H264
    bit_depth: int = 8
    rate_control: RateControl = field(default_factory=lambda: ConstantQuality(23))
    preset: str | int | None = None
    tune: str | None = None
    profile: str | None = None
    level: str | None = None
    resolution_limit: ResolutionLimit = ResolutionLimit.NONE
    width: int | None = None
    height: int | None = None
    allow_upscale: bool = False
    crop: str = "none"
    rotation: int = 0
    flip: str | None = None
    frame_rate: str = "source"
    frame_rate_mode: str = "source"
    color_policy: str = "preserve"
    color_range: str | None = None
    deinterlace: str = "auto"

    def __post_init__(self) -> None:
        if self.bit_depth not in (8, 10):
            raise ValueError("video bit depth must be 8 or 10")
        if self.crop not in ("none", "auto"):
            raise ValueError("crop must be none or auto")
        if self.rotation not in (0, 90, 180, 270):
            raise ValueError("rotation must be 0, 90, 180, or 270")
        if self.flip not in (None, "horizontal", "vertical"):
            raise ValueError("flip must be horizontal or vertical")
        if self.frame_rate_mode not in ("source", "cfr", "vfr"):
            raise ValueError("frame rate mode must be source, cfr, or vfr")
        if self.color_policy not in ("preserve", "override"):
            raise ValueError("color policy must be preserve or override")
        if self.deinterlace not in ("auto", "off", "on"):
            raise ValueError("deinterlace must be auto, off, or on")


@dataclass(frozen=True)
class AudioOptions:
    tracks: Selection = Selection.FIRST
    codec: AudioCodec = AudioCodec.COPY
    bitrate: int | None = None
    channels: str = "source"
    sample_rate: str | int = "source"


@dataclass(frozen=True)
class SubtitleOptions:
    tracks: SubtitleSelection = SubtitleSelection.NONE
    mode: SubtitleMode = SubtitleMode.COPY


@dataclass(frozen=True)
class OutputOptions:
    container: Container | None = None
    metadata: str = "copy"
    chapters: str = "copy"
    overwrite: bool = False


@dataclass(frozen=True)
class StreamInfo:
    index: int
    codec_type: str
    codec_name: str | None = None
    width: int | None = None
    height: int | None = None
    pixel_format: str | None = None
    bit_depth: int | None = None
    avg_frame_rate: str | None = None
    real_frame_rate: str | None = None
    time_base: str | None = None
    sample_aspect_ratio: str | None = None
    display_aspect_ratio: str | None = None
    color_range: str | None = None
    color_space: str | None = None
    color_primaries: str | None = None
    color_transfer: str | None = None
    channels: int | None = None
    channel_layout: str | None = None
    sample_rate: int | None = None
    bit_rate: int | None = None
    language: str | None = None
    title: str | None = None
    disposition: dict[str, int] = field(default_factory=dict)
    side_data: tuple[dict[str, Any], ...] = ()
    field_order: str | None = None


@dataclass(frozen=True)
class ChapterInfo:
    id: int
    start: float
    end: float
    tags: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    format_names: tuple[str, ...]
    duration: float | None
    bit_rate: int | None
    tags: dict[str, str]
    streams: tuple[StreamInfo, ...]
    chapters: tuple[ChapterInfo, ...]

    @property
    def video_streams(self) -> tuple[StreamInfo, ...]:
        return tuple(s for s in self.streams if s.codec_type == "video")

    @property
    def audio_streams(self) -> tuple[StreamInfo, ...]:
        return tuple(s for s in self.streams if s.codec_type == "audio")

    @property
    def subtitle_streams(self) -> tuple[StreamInfo, ...]:
        return tuple(s for s in self.streams if s.codec_type == "subtitle")


@dataclass(frozen=True)
class TranscodeJob:
    input_path: Path
    output_path: Path
    command: tuple[str, ...]
    output_width: int | None
    output_height: int | None
    warnings: tuple[str, ...] = ()
    resolved_crop: str = "none"
    resolved_deinterlace: str = "off"
    crop_rect: CropRect | None = None


@dataclass(frozen=True)
class TranscodeResult:
    job: TranscodeJob
    returncode: int
    stderr: str
    elapsed_seconds: float = 0.0
    output_size: int | None = None
    source_size: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass(frozen=True)
class ProgressEvent:
    percent: float | None
    encoded_seconds: float
    duration_seconds: float | None
    fps: float | None
    speed: float | None
    output_size: int | None
    elapsed_seconds: float
    finished: bool = False
    estimated_remaining_seconds: float | None = None
