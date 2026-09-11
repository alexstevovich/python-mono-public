import unittest
from pathlib import Path

from video_transcode import MediaInfo, StreamInfo, VideoOptions, build_transcode_job
from video_transcode.filters import deinterlace_filter


class DeinterlaceTests(unittest.TestCase):
    def setUp(self):
        self.media = MediaInfo(
            Path("in.mkv"),
            ("matroska",),
            1.0,
            None,
            {},
            (StreamInfo(0, "video", "h264", 640, 480),),
            (),
        )

    def test_auto_is_selective_and_single_rate(self):
        filter_text, resolved = deinterlace_filter("auto")
        self.assertIn("deint=interlaced", filter_text)
        self.assertIn("mode=send_frame", filter_text)
        self.assertIn("flagged frames only", resolved)

    def test_forced_on_deinterlaces_all_frames_at_single_rate(self):
        filter_text, resolved = deinterlace_filter("on")
        self.assertIn("deint=all", filter_text)
        self.assertIn("mode=send_frame", filter_text)
        self.assertIn("single-rate", resolved)

    def test_forced_off_adds_no_filter(self):
        filter_text, resolved = deinterlace_filter("off")
        self.assertIsNone(filter_text)
        self.assertEqual(resolved, "off")
        job = build_transcode_job(
            "in.mkv", "out.mkv", media=self.media, video=VideoOptions(deinterlace="off")
        )
        self.assertFalse(any("bwdif" in value for value in job.command))
