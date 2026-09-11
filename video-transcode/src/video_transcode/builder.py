from __future__ import annotations

import shutil
from pathlib import Path

from .errors import BinaryNotFoundError, ValidationError
from .filters import deinterlace_filter
from .models import (
    AudioCodec,
    AudioOptions,
    ConstantQuality,
    Container,
    CropAnalysis,
    CropRect,
    MediaInfo,
    OutputOptions,
    Selection,
    StreamInfo,
    SubtitleMode,
    SubtitleOptions,
    SubtitleSelection,
    TranscodeJob,
    VideoCodec,
    VideoOptions,
)
from .scaling import explicit_dimensions, fit_dimensions
from .validation import validate_options

ENCODERS = {
    VideoCodec.SVT_AV1: "libsvtav1",
    VideoCodec.AV1_NVENC: "av1_nvenc",
    VideoCodec.H264: "libx264",
    VideoCodec.H265: "libx265",
}
AUDIO_ENCODERS = {
    AudioCodec.COPY: "copy",
    AudioCodec.OPUS: "libopus",
    AudioCodec.AAC: "aac",
}
PIX_FMTS = {
    VideoCodec.SVT_AV1: {8: "yuv420p", 10: "yuv420p10le"},
    VideoCodec.AV1_NVENC: {8: "yuv420p", 10: "p010le"},
    VideoCodec.H264: {8: "yuv420p", 10: "yuv420p10le"},
    VideoCodec.H265: {8: "yuv420p", 10: "yuv420p10le"},
}


def _select(
    streams: tuple[StreamInfo, ...], choice: Selection | SubtitleSelection
) -> tuple[StreamInfo, ...]:
    if choice == "none":
        return ()
    if choice == "first":
        return streams[:1]
    if choice == "forced":
        return tuple(s for s in streams if s.disposition.get("forced") == 1)
    return streams


def _filters(
    video: VideoOptions,
    source: StreamInfo,
    subtitles: SubtitleOptions,
    input_path: Path,
    crop_analysis: CropAnalysis | None,
) -> tuple[list[str], int, int, list[str], CropRect | None]:
    width, height = source.width, source.height
    if not width or not height:
        raise ValidationError("the selected video stream has no dimensions")
    filters: list[str] = []
    warnings: list[str] = []
    crop_rect = (
        crop_analysis.crop if crop_analysis and crop_analysis.conclusive else None
    )
    if crop_rect:
        filters.append(
            f"crop={crop_rect.width}:{crop_rect.height}:{crop_rect.x}:{crop_rect.y}"
        )
        width, height = crop_rect.width, crop_rect.height
    elif video.crop == "auto" and (
        crop_analysis is None or not crop_analysis.conclusive
    ):
        warnings.append(
            "automatic crop analysis was inconclusive; output left uncropped"
        )
    width, height = fit_dimensions(
        width, height, video.resolution_limit, video.allow_upscale
    )
    width, height = explicit_dimensions(
        width, height, video.width, video.height, video.allow_upscale
    )
    if (width, height) != (
        (crop_rect.width, crop_rect.height)
        if crop_rect
        else (source.width, source.height)
    ):
        filters.append(f"scale={width}:{height}")
    deinterlace, _ = deinterlace_filter(video.deinterlace)
    if deinterlace:
        filters.append(deinterlace)
    if video.rotation == 90:
        filters.append("transpose=clock")
    elif video.rotation == 180:
        filters.extend(["hflip", "vflip"])
    elif video.rotation == 270:
        filters.append("transpose=cclock")
    if video.flip == "horizontal":
        filters.append("hflip")
    elif video.flip == "vertical":
        filters.append("vflip")
    if subtitles.mode == SubtitleMode.BURN:
        selected = _select((), subtitles.tracks)
        del selected
        safe_path = (
            str(input_path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        )
        filters.append(f"subtitles='{safe_path}':si=0")
    return filters, width, height, warnings, crop_rect


def build_transcode_job(
    input_path: str | Path,
    output_path: str | Path,
    *,
    media: MediaInfo,
    video: VideoOptions | None = None,
    audio: AudioOptions | None = None,
    subtitles: SubtitleOptions | None = None,
    output: OutputOptions | None = None,
    ffmpeg: str = "ffmpeg",
    require_binary: bool = False,
    progress: bool = False,
    crop_analysis: CropAnalysis | None = None,
) -> TranscodeJob:
    video, audio, subtitles, output = (
        video or VideoOptions(),
        audio or AudioOptions(),
        subtitles or SubtitleOptions(),
        output or OutputOptions(),
    )
    container = validate_options(video, audio, subtitles, output, output_path)
    if not media.video_streams:
        raise ValidationError("input has no video stream")
    binary = shutil.which(ffmpeg)
    if require_binary and not binary:
        raise BinaryNotFoundError(
            "ffmpeg was not found on PATH; install FFmpeg and ensure ffmpeg is available"
        )
    cmd = [binary or ffmpeg, "-hide_banner", "-nostdin"]
    if progress:
        cmd += ["-loglevel", "error", "-progress", "pipe:1", "-nostats"]
    cmd += [
        "-y" if output.overwrite else "-n",
        "-i",
        str(input_path),
        "-map",
        f"0:{media.video_streams[0].index}",
    ]
    selected_audio = _select(media.audio_streams, audio.tracks)
    selected_subs = (
        ()
        if subtitles.mode == SubtitleMode.BURN
        else _select(media.subtitle_streams, subtitles.tracks)
    )
    for s in selected_audio:
        cmd += ["-map", f"0:{s.index}"]
    for s in selected_subs:
        cmd += ["-map", f"0:{s.index}"]
    cmd += [
        "-c:v",
        ENCODERS[video.codec],
        "-pix_fmt",
        PIX_FMTS[video.codec][video.bit_depth],
    ]
    if isinstance(video.rate_control, ConstantQuality):
        if video.codec == VideoCodec.SVT_AV1:
            cmd += ["-crf", str(video.rate_control.value)]
        elif video.codec == VideoCodec.AV1_NVENC:
            cmd += ["-cq", str(video.rate_control.value), "-rc", "vbr"]
        else:
            cmd += ["-crf", str(video.rate_control.value)]
    else:
        cmd += ["-b:v", str(video.rate_control.bitrate)]
    if video.preset is not None:
        cmd += ["-preset", str(video.preset)]
    if video.tune:
        if video.codec == VideoCodec.SVT_AV1:
            svt_tunes = {"vq": "0", "psnr": "1", "ssim": "2"}
            if video.tune.lower() not in svt_tunes:
                raise ValidationError("SVT-AV1 tune must be vq, psnr, or ssim")
            cmd += ["-svtav1-params", f"tune={svt_tunes[video.tune.lower()]}"]
        else:
            cmd += ["-tune", video.tune]
    if video.profile:
        cmd += ["-profile:v", video.profile]
    if video.level:
        cmd += ["-level:v", video.level]
    filters, out_w, out_h, warnings, crop_rect = _filters(
        video, media.video_streams[0], subtitles, Path(input_path), crop_analysis
    )
    if filters:
        cmd += ["-vf", ",".join(filters)]
    if video.frame_rate != "source":
        cmd += ["-r", video.frame_rate]
    if video.frame_rate_mode == "cfr":
        cmd += ["-fps_mode", "cfr"]
    elif video.frame_rate_mode == "vfr":
        cmd += ["-fps_mode", "vfr"]
    else:
        cmd += ["-fps_mode", "passthrough"]
    if video.color_range:
        cmd += ["-color_range", video.color_range]
    if selected_audio:
        cmd += ["-c:a", AUDIO_ENCODERS[audio.codec]]
        if audio.codec != AudioCodec.COPY:
            if audio.bitrate:
                cmd += ["-b:a", str(audio.bitrate)]
            if audio.channels != "source":
                cmd += ["-ac", {"mono": "1", "stereo": "2", "5.1": "6"}[audio.channels]]
            if audio.sample_rate != "source":
                cmd += ["-ar", str(audio.sample_rate)]
    if selected_subs:
        subtitle_codec = (
            "copy"
            if subtitles.mode == SubtitleMode.COPY
            else (
                "mov_text"
                if container in (Container.MP4, Container.MOV)
                else "webvtt"
                if container == Container.WEBM
                else "srt"
            )
        )
        cmd += ["-c:s", subtitle_codec]
    cmd += [
        "-map_metadata",
        "0" if output.metadata == "copy" else "-1",
        "-map_chapters",
        "0" if output.chapters == "copy" else "-1",
    ]
    if container in (Container.MP4, Container.MOV):
        cmd += ["-movflags", "+faststart"]
    cmd.append(str(output_path))
    _, resolved_deinterlace = deinterlace_filter(video.deinterlace)
    resolved_crop = f"{crop_rect.width}x{crop_rect.height}" if crop_rect else "none"
    return TranscodeJob(
        Path(input_path),
        Path(output_path),
        tuple(cmd),
        out_w,
        out_h,
        tuple(warnings),
        resolved_crop,
        resolved_deinterlace,
        crop_rect,
    )
