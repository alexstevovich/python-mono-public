import unittest
from pathlib import Path

from video_transcode import (
    AudioCodec,
    AudioOptions,
    AverageBitrate,
    ConstantQuality,
    MediaInfo,
    OutputOptions,
    ResolutionLimit,
    Selection,
    StreamInfo,
    SubtitleMode,
    SubtitleOptions,
    SubtitleSelection,
    ValidationError,
    VideoCodec,
    VideoOptions,
    build_transcode_job,
    parse_probe,
)
from video_transcode.scaling import fit_dimensions


def media(*streams):
    return MediaInfo(Path("in.mkv"), ("matroska",), 1.0, None, {}, tuple(streams), ())


class CoreTests(unittest.TestCase):
    def test_scaling_landscape_portrait_and_no_upscale(self):
        self.assertEqual(
            fit_dimensions(3840, 2160, ResolutionLimit.HD_1080), (1920, 1080)
        )
        self.assertEqual(
            fit_dimensions(2160, 3840, ResolutionLimit.HD_1080), (1080, 1920)
        )
        self.assertEqual(
            fit_dimensions(1280, 720, ResolutionLimit.HD_1080), (1280, 720)
        )

    def test_deterministic_manual_target_command(self):
        info = media(
            StreamInfo(0, "video", "h264", 3840, 2160),
            StreamInfo(1, "audio", "aac", language="eng"),
            StreamInfo(2, "audio", "aac", language="jpn"),
            StreamInfo(3, "subtitle", "subrip"),
        )
        kwargs = dict(
            media=info,
            video=VideoOptions(
                VideoCodec.SVT_AV1,
                10,
                ConstantQuality(40),
                2,
                "vq",
                resolution_limit=ResolutionLimit.HD_1080,
            ),
            audio=AudioOptions(Selection.ALL, AudioCodec.OPUS, 128000, "stereo"),
            subtitles=SubtitleOptions(SubtitleSelection.ALL, SubtitleMode.COPY),
            output=OutputOptions(),
        )
        one = build_transcode_job("in.mkv", "out.mkv", **kwargs)
        two = build_transcode_job("in.mkv", "out.mkv", **kwargs)
        self.assertEqual(one.command, two.command)
        self.assertEqual((one.output_width, one.output_height), (1920, 1080))
        self.assertEqual(one.command.count("-map"), 4)
        for value in ("libsvtav1", "yuv420p10le", "libopus", "tune=0"):
            self.assertIn(value, one.command)
        self.assertNotIn("-tune", one.command)

    def test_webm_rejects_h264(self):
        info = media(StreamInfo(0, "video", "h264", 1280, 720))
        with self.assertRaisesRegex(ValidationError, "WebM"):
            build_transcode_job("in.mkv", "out.webm", media=info)

    def test_mp4_rejects_subtitle_passthrough(self):
        info = media(
            StreamInfo(0, "video", "h264", 1280, 720),
            StreamInfo(1, "subtitle", "subrip"),
        )
        with self.assertRaisesRegex(ValidationError, "subtitle copy"):
            build_transcode_job(
                "in.mkv",
                "out.mp4",
                media=info,
                subtitles=SubtitleOptions(SubtitleSelection.ALL, SubtitleMode.COPY),
            )

    def test_two_pass_and_copy_with_transform_are_explicit_errors(self):
        info = media(
            StreamInfo(0, "video", "h264", 1280, 720), StreamInfo(1, "audio", "aac")
        )
        with self.assertRaisesRegex(ValidationError, "two-pass"):
            build_transcode_job(
                "in.mkv",
                "out.mkv",
                media=info,
                video=VideoOptions(rate_control=AverageBitrate(1_000_000, 2)),
            )
        with self.assertRaisesRegex(ValidationError, "not copy"):
            build_transcode_job(
                "in.mkv",
                "out.mkv",
                media=info,
                audio=AudioOptions(codec=AudioCodec.COPY, channels="stereo"),
            )

    def test_parse_probe_preserves_metadata(self):
        raw = {
            "format": {
                "format_name": "matroska,webm",
                "duration": "1.5",
                "tags": {"title": "Demo"},
            },
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "pix_fmt": "yuv420p",
                    "color_primaries": "bt709",
                    "tags": {"language": "eng"},
                    "disposition": {"default": 1},
                },
                {
                    "index": 1,
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "channels": 2,
                    "sample_rate": "48000",
                    "tags": {"language": "fra"},
                },
            ],
            "chapters": [
                {
                    "id": 0,
                    "start_time": "0",
                    "end_time": "1.5",
                    "tags": {"title": "One"},
                }
            ],
        }
        parsed = parse_probe(raw, "in.mkv")
        self.assertEqual(parsed.tags["title"], "Demo")
        self.assertEqual(parsed.video_streams[0].color_primaries, "bt709")
        self.assertEqual(parsed.audio_streams[0].language, "fra")
        self.assertEqual(parsed.chapters[0].tags["title"], "One")
