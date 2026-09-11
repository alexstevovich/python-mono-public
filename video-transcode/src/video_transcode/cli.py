from __future__ import annotations

import argparse
import json
import shlex
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .binary import find_media_tools
from .builder import build_transcode_job
from .colors import ERROR, INFO, PROGRESS, SUCCESS, TITLE, WARNING, paint
from .cropping import analyze_crop
from .errors import ValidationError, VideoTranscodeError
from .executor import execute_job
from .models import (
    AudioCodec,
    AudioOptions,
    AverageBitrate,
    ConstantQuality,
    Container,
    MediaInfo,
    OutputOptions,
    ProgressEvent,
    ResolutionLimit,
    Selection,
    SubtitleMode,
    SubtitleOptions,
    SubtitleSelection,
    TranscodeJob,
    VideoCodec,
    VideoOptions,
)
from .probe import probe_media


def bitrate(value: str) -> int:
    multipliers = {"k": 1000, "m": 1_000_000}
    try:
        return (
            int(float(value[:-1]) * multipliers[value[-1].lower()])
            if value[-1].lower() in multipliers
            else int(value)
        )
    except (ValueError, IndexError) as exc:
        raise argparse.ArgumentTypeError(
            "use bits/s or a suffix such as 128k or 2m"
        ) from exc


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="video-transcode",
        description="Explicit FFmpeg video transcoding without a preset system",
    )
    root.add_argument("input", type=Path, help="source media file")
    root.add_argument("output", type=Path, help="destination media file")
    root.add_argument(
        "--video-codec", choices=[x.value for x in VideoCodec], default="h264"
    )
    root.add_argument("--video-bit-depth", type=int, choices=(8, 10), default=8)
    rc = root.add_mutually_exclusive_group()
    rc.add_argument("--video-quality", type=float, default=23)
    rc.add_argument("--video-bitrate", type=bitrate)
    root.add_argument("--video-passes", type=int, choices=(1, 2), default=1)
    root.add_argument("--video-preset")
    root.add_argument("--video-tune")
    root.add_argument("--video-profile")
    root.add_argument("--video-level")
    root.add_argument(
        "--resolution-limit", choices=[x.value for x in ResolutionLimit], default="none"
    )
    root.add_argument("--width", type=int)
    root.add_argument("--height", type=int)
    upscale = root.add_mutually_exclusive_group()
    upscale.add_argument("--allow-upscale", dest="allow_upscale", action="store_true")
    upscale.add_argument("--no-upscale", dest="allow_upscale", action="store_false")
    root.set_defaults(allow_upscale=False)
    root.add_argument("--crop", choices=("none", "auto"), default="none")
    root.add_argument("--rotate", type=int, choices=(0, 90, 180, 270), default=0)
    root.add_argument("--flip", choices=("horizontal", "vertical"))
    root.add_argument("--frame-rate", default="source")
    root.add_argument(
        "--frame-rate-mode", choices=("source", "cfr", "vfr"), default="source"
    )
    root.add_argument(
        "--color-policy", choices=("preserve", "override"), default="preserve"
    )
    root.add_argument("--color-range", choices=("tv", "pc"))
    root.add_argument(
        "--deinterlace",
        choices=("auto", "off", "on"),
        default="auto",
        help="deinterlace flagged frames automatically (default), disable it, or force it for every frame",
    )
    root.add_argument(
        "--audio-tracks", choices=[x.value for x in Selection], default="first"
    )
    root.add_argument(
        "--audio-codec", choices=[x.value for x in AudioCodec], default="copy"
    )
    root.add_argument("--audio-bitrate", type=bitrate)
    root.add_argument(
        "--audio-channels",
        choices=("source", "mono", "stereo", "5.1"),
        default="source",
    )
    root.add_argument("--audio-sample-rate", default="source")
    root.add_argument(
        "--subtitles", choices=[x.value for x in SubtitleSelection], default="none"
    )
    root.add_argument(
        "--subtitle-mode", choices=[x.value for x in SubtitleMode], default="copy"
    )
    root.add_argument("--container", choices=[x.value for x in Container])
    root.add_argument("--metadata", choices=("copy", "none"), default="copy")
    root.add_argument("--chapters", choices=("copy", "none"), default="copy")
    root.add_argument("--overwrite", action="store_true")
    root.add_argument("--dry-run", action="store_true")
    return root


def probe_parser() -> argparse.ArgumentParser:
    probe = argparse.ArgumentParser(
        prog="video-transcode probe", description="Print normalized media information"
    )
    probe.add_argument("input", type=Path, help="media file to inspect")
    return probe


def _options(a: argparse.Namespace):
    rate = (
        AverageBitrate(a.video_bitrate, a.video_passes)
        if a.video_bitrate
        else ConstantQuality(a.video_quality)
    )
    video = VideoOptions(
        VideoCodec(a.video_codec),
        a.video_bit_depth,
        rate,
        a.video_preset,
        a.video_tune,
        a.video_profile,
        a.video_level,
        ResolutionLimit(a.resolution_limit),
        a.width,
        a.height,
        a.allow_upscale,
        a.crop,
        a.rotate,
        a.flip,
        a.frame_rate,
        a.frame_rate_mode,
        a.color_policy,
        a.color_range,
        a.deinterlace,
    )
    sample_rate = (
        a.audio_sample_rate
        if a.audio_sample_rate == "source"
        else int(a.audio_sample_rate)
    )
    audio = AudioOptions(
        Selection(a.audio_tracks),
        AudioCodec(a.audio_codec),
        a.audio_bitrate,
        a.audio_channels,
        sample_rate,
    )
    subtitles = SubtitleOptions(
        SubtitleSelection(a.subtitles), SubtitleMode(a.subtitle_mode)
    )
    output = OutputOptions(
        Container(a.container) if a.container else None,
        a.metadata,
        a.chapters,
        a.overwrite,
    )
    return video, audio, subtitles, output


def _normalize_argv(argv: list[str]) -> list[str]:
    arguments = list(argv)
    if arguments and arguments[0] == "transcode":
        arguments.pop(0)
    return arguments


def _duration(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    minutes, second = divmod(max(0, int(seconds)), 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours:02d}:{minute:02d}:{second:02d}"


def _size(value: int | None) -> str:
    if value is None:
        return "unknown"
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if amount < 1024 or unit == "GiB":
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} GiB"


def _progress_line(event: ProgressEvent) -> None:
    percent = f"{event.percent:6.2f}%" if event.percent is not None else "   ---%"
    fps = f"{event.fps:.1f} fps" if event.fps is not None else "-- fps"
    speed = f"{event.speed:.2f}x" if event.speed is not None else "--x"
    line = f"  {percent} | {_duration(event.encoded_seconds)} / {_duration(event.duration_seconds)} | {fps} | {speed} | {_size(event.output_size)} | elapsed {_duration(event.elapsed_seconds)} | ETA {_duration(event.estimated_remaining_seconds)}"
    print("\r" + paint(line, PROGRESS), end="", flush=True)


def _print_start_summary(
    args: argparse.Namespace,
    media: MediaInfo,
    job: TranscodeJob,
    video: VideoOptions,
    audio: AudioOptions,
    subtitles: SubtitleOptions,
    output: OutputOptions,
    started_at: datetime,
) -> None:
    source = media.video_streams[0]
    container = (
        output.container or Container(args.output.suffix.lstrip(".").lower())
    ).value
    print(paint("Video Transcode", TITLE))
    print("  Operation:     Transcode")
    print(f"  Source:        {args.input}")
    print(
        f"  Source size:   {_size(args.input.stat().st_size if args.input.exists() else None)}"
    )
    print(f"  Destination:   {args.output}")
    print(f"  Started:       {started_at:%Y-%m-%d %H:%M:%S}")
    print(f"\n  Container:     {container}")
    codec_name = {
        VideoCodec.SVT_AV1: "SVT-AV1",
        VideoCodec.AV1_NVENC: "AV1 NVENC",
        VideoCodec.H264: "H.264 / x264",
        VideoCodec.H265: "H.265 / x265",
    }[video.codec]
    quality = (
        f"CRF {video.rate_control.value:g}"
        if isinstance(video.rate_control, ConstantQuality)
        else f"{video.rate_control.bitrate / 1000:g} kbps"
    )
    print(paint("\n  Video:", INFO))
    print(f"    Codec:       {codec_name}")
    print(f"    Bit depth:   {video.bit_depth}-bit")
    print(f"    Quality:     {quality}")
    print(f"    Preset:      {video.preset or 'default'}")
    print(f"    Tune:        {video.tune.upper() if video.tune else 'default'}")
    print(
        f"    Resolution:  {source.width}x{source.height} -> {job.output_width}x{job.output_height}"
    )
    frame_mode = {"source": "source timing", "cfr": "CFR", "vfr": "VFR"}[
        video.frame_rate_mode
    ]
    print(f"    Frame rate:  {video.frame_rate} / {frame_mode}")
    print(f"    Color:       {video.color_policy}")
    print(
        f"    Crop:        {video.crop}"
        + (f" -> {job.resolved_crop} detected" if video.crop == "auto" else "")
    )
    if job.crop_rect:
        top, bottom, left, right = job.crop_rect.margins(source.width, source.height)
        print(
            f"                 top {top}, bottom {bottom}, left {left}, right {right}"
        )
    print(f"    Deinterlace: {video.deinterlace} -> {job.resolved_deinterlace}")
    print(paint("\n  Audio:", INFO))
    print(f"    Tracks:      {audio.tracks.value}")
    print(f"    Codec:       {audio.codec.value}")
    print(
        f"    Bitrate:     {audio.bitrate / 1000:g} kbps"
        if audio.bitrate
        else "    Bitrate:     source/default"
    )
    print(f"    Channels:    {audio.channels}")
    print(paint("\n  Subtitles:", INFO))
    print(f"    Tracks:      {subtitles.tracks.value}")
    print(f"    Mode:        {subtitles.mode.value}")
    print(f"\n  Metadata:      {output.metadata}")
    print(f"  Chapters:      {output.chapters}\n")
    for warning in job.warnings:
        print(paint(f"Warning: {warning}", WARNING, sys.stderr), file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = _normalize_argv(list(sys.argv[1:] if argv is None else argv))
        if arguments and arguments[0] == "probe":
            args = probe_parser().parse_args(arguments[1:])
            print(json.dumps(asdict(probe_media(args.input)), indent=2, default=str))
            return 0
        args = parser().parse_args(arguments)
        video, audio, subtitles, output = _options(args)
        if args.dry_run:
            tools = find_media_tools()
            media = probe_media(args.input, ffprobe=tools.ffprobe)
            crop_analysis = (
                analyze_crop(args.input, media, ffmpeg=tools.ffmpeg)
                if video.crop == "auto"
                else None
            )
            job = build_transcode_job(
                args.input,
                args.output,
                media=media,
                video=video,
                audio=audio,
                subtitles=subtitles,
                output=output,
                ffmpeg=tools.ffmpeg,
                require_binary=True,
                crop_analysis=crop_analysis,
            )
            print(
                f"Resolved video: {media.video_streams[0].width}x{media.video_streams[0].height} -> {job.output_width}x{job.output_height}"
            )
            print(f"Resolved crop: {video.crop} -> {job.resolved_crop}")
            if job.crop_rect:
                source = media.video_streams[0]
                top, bottom, left, right = job.crop_rect.margins(
                    source.width, source.height
                )
                print(
                    f"Crop margins: top {top}, bottom {bottom}, left {left}, right {right}"
                )
            print(
                f"Audio tracks: {audio.tracks.value}; subtitles: {subtitles.tracks.value}/{subtitles.mode.value}"
            )
            for warning in job.warnings:
                print(f"Warning: {warning}", file=sys.stderr)
            print(shlex.join(job.command))
            return 0
        if args.output.exists() and not output.overwrite:
            raise ValidationError(
                f"output already exists: {args.output}; pass --overwrite to replace it"
            )
        tools = find_media_tools()
        media = probe_media(args.input, ffprobe=tools.ffprobe)
        crop_analysis = (
            analyze_crop(args.input, media, ffmpeg=tools.ffmpeg)
            if video.crop == "auto"
            else None
        )
        job = build_transcode_job(
            args.input,
            args.output,
            media=media,
            video=video,
            audio=audio,
            subtitles=subtitles,
            output=output,
            ffmpeg=tools.ffmpeg,
            require_binary=True,
            progress=True,
            crop_analysis=crop_analysis,
        )
        started_at = datetime.now().astimezone()
        _print_start_summary(
            args, media, job, video, audio, subtitles, output, started_at
        )
        result = execute_job(
            job,
            duration=media.duration,
            progress_callback=_progress_line,
            started_at=started_at,
        )
        print()
        print(paint("Completed", SUCCESS))
        print(f"  Started:       {result.started_at:%Y-%m-%d %H:%M:%S}")
        print(f"  Finished:      {result.finished_at:%Y-%m-%d %H:%M:%S}")
        print(f"  Elapsed:       {_duration(result.elapsed_seconds)}")
        print(f"\n  Input size:    {_size(result.source_size)}")
        print(f"  Output size:   {_size(result.output_size)}")
        reduction = (
            100 * (1 - result.output_size / result.source_size)
            if result.source_size and result.output_size is not None
            else None
        )
        print(
            f"  Reduction:     {reduction:.1f}%"
            if reduction is not None
            else "  Reduction:     unavailable"
        )
        print(f"\n  Destination:   {result.job.output_path}")
        return 0
    except (VideoTranscodeError, ValueError) as exc:
        print(paint(f"error: {exc}", ERROR, sys.stderr), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
