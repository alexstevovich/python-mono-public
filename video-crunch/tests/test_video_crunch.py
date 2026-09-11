import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from video_crunch import DEFAULT_VIDEO_PATTERNS, Status, VideoCrunchPreset, run
from video_crunch.core import crunch, discover


class VideoCrunchTests(unittest.TestCase):
    def test_discovery_respects_recursion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            direct = root / "direct.mp4"
            nested = root / "nested" / "nested.mkv"
            nested.parent.mkdir()
            direct.touch()
            nested.touch()
            self.assertEqual(
                discover([root], recursive=False, patterns=DEFAULT_VIDEO_PATTERNS),
                [direct],
            )
            self.assertEqual(
                discover([root], recursive=True, patterns=DEFAULT_VIDEO_PATTERNS),
                [direct, nested],
            )

    def test_candidate_must_meet_maximum_size_ratio(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "video.mp4"
            source.write_bytes(b"x" * 100)

            kept = crunch(
                source,
                lambda _source, candidate: candidate.write_bytes(b"y" * 91) and 0,
                max_size_ratio=0.9,
                output_suffix=".mkv",
            )
            self.assertEqual(kept.status, Status.KEPT)
            self.assertTrue(source.exists())

            replaced = crunch(
                source,
                lambda _source, candidate: candidate.write_bytes(b"y" * 80) and 0,
                max_size_ratio=0.9,
                output_suffix=".mkv",
            )
            self.assertEqual(replaced.status, Status.REPLACED)
            self.assertFalse(source.exists())
            self.assertEqual(source.with_suffix(".mkv").stat().st_size, 80)

    @patch("video_crunch.cli.transcode_main")
    def test_runner_calls_transcoder_directly_with_preset_arguments(
        self, transcode_main
    ):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "video.mp4"
            source.write_bytes(b"x" * 100)

            def transcode(argv):
                Path(argv[1]).write_bytes(b"y" * 50)
                return 0

            transcode_main.side_effect = transcode
            preset = VideoCrunchPreset("test-crunch", "Test", ("--video-codec", "h265"))
            self.assertEqual(run(preset, [str(source)]), 0)
            self.assertEqual(
                transcode_main.call_args.args[0][-2:], ["--video-codec", "h265"]
            )


if __name__ == "__main__":
    unittest.main()
