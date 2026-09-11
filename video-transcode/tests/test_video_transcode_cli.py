import unittest

from video_transcode.cli import _normalize_argv, parser


class CliTests(unittest.TestCase):
    def test_no_upscale_flag_spelling(self):
        args = parser().parse_args(["in.mkv", "out.mkv", "--allow-upscale"])
        self.assertTrue(args.allow_upscale)
        args = parser().parse_args(["in.mkv", "out.mkv", "--no-upscale"])
        self.assertFalse(args.allow_upscale)

    def test_direct_form_is_normalized_to_transcode(self):
        self.assertEqual(
            _normalize_argv(["in.mp4", "out.mkv", "--dry-run"]),
            ["in.mp4", "out.mkv", "--dry-run"],
        )

    def test_legacy_explicit_transcode_is_accepted(self):
        self.assertEqual(
            _normalize_argv(["transcode", "in.mp4", "out.mkv"]), ["in.mp4", "out.mkv"]
        )

    def test_deinterlace_defaults_to_auto(self):
        args = parser().parse_args(["in.mkv", "out.mkv"])
        self.assertEqual(args.deinterlace, "auto")
