import unittest

from video_transcode import parse_progress


class ProgressTests(unittest.TestCase):
    def test_machine_progress_is_normalized(self):
        event = parse_progress(
            {
                "out_time_us": "5000000",
                "fps": "42.5",
                "speed": "0.82x",
                "total_size": "1048576",
                "progress": "continue",
            },
            duration=10.0,
            elapsed=6.25,
        )
        self.assertEqual(event.percent, 50.0)
        self.assertEqual(event.encoded_seconds, 5.0)
        self.assertEqual(event.fps, 42.5)
        self.assertEqual(event.speed, 0.82)
        self.assertEqual(event.output_size, 1_048_576)
        self.assertEqual(event.elapsed_seconds, 6.25)
        self.assertAlmostEqual(event.estimated_remaining_seconds, 5.0 / 0.82)
        self.assertFalse(event.finished)

    def test_finished_event_reaches_100_percent(self):
        event = parse_progress(
            {"out_time_us": "9900000", "progress": "end"}, duration=10.0, elapsed=3.0
        )
        self.assertEqual(event.percent, 100.0)
        self.assertTrue(event.finished)
