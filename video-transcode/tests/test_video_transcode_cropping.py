import unittest
from pathlib import Path

from video_transcode import (
    CropAnalysis,
    CropRect,
    MediaInfo,
    ResolutionLimit,
    StreamInfo,
    VideoOptions,
    build_transcode_job,
    choose_crop,
)


class CropConsensusTests(unittest.TestCase):
    def test_no_border_progressive_video_resolves_to_none(self):
        full = CropRect(1920, 1080, 0, 0)
        result = choose_crop((full,) * 5, 1920, 1080, 5)
        self.assertTrue(result.conclusive)
        self.assertIsNone(result.crop)

    def test_letterbox_consensus_ignores_black_intro_outlier(self):
        letterbox = CropRect(1920, 800, 0, 140)
        black_frame_outlier = CropRect(320, 240, 800, 420)
        result = choose_crop(
            (black_frame_outlier, letterbox, letterbox, letterbox, letterbox),
            1920,
            1080,
            5,
        )
        self.assertEqual(result.crop, letterbox)

    def test_pillarbox_is_detected(self):
        pillarbox = CropRect(1440, 1080, 240, 0)
        result = choose_crop((pillarbox,) * 5, 1920, 1080, 5)
        self.assertEqual(result.crop, pillarbox)

    def test_inconsistent_results_fall_back_to_none(self):
        candidates = (
            CropRect(1920, 800, 0, 140),
            CropRect(1920, 900, 0, 90),
            CropRect(1440, 1080, 240, 0),
            CropRect(1600, 900, 160, 90),
            CropRect(1800, 1000, 60, 40),
        )
        result = choose_crop(candidates, 1920, 1080, 5)
        self.assertFalse(result.conclusive)
        self.assertIsNone(result.crop)

    def test_crop_precedes_1080p_scaling(self):
        media = MediaInfo(
            Path("in.mkv"),
            ("matroska",),
            10.0,
            None,
            {},
            (StreamInfo(0, "video", "h264", 3840, 2160),),
            (),
        )
        crop = CropRect(3840, 1600, 0, 280)
        analysis = CropAnalysis(crop, True, 5, 5, (crop,) * 5)
        job = build_transcode_job(
            "in.mkv",
            "out.mkv",
            media=media,
            video=VideoOptions(
                crop="auto", resolution_limit=ResolutionLimit.HD_1080, deinterlace="off"
            ),
            crop_analysis=analysis,
        )
        filters = job.command[job.command.index("-vf") + 1]
        self.assertEqual(filters, "crop=3840:1600:0:280,scale=1920:800")
        self.assertEqual((job.output_width, job.output_height), (1920, 800))
