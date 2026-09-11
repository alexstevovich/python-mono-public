import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from comfyui_metadata import Metadata, metadata_for_webp, read_metadata
from image_convert import EncodeOptions, Transform, convert_to_webp
from image_crunch import (
    ImageCrunchPreset,
    ResolutionPreset,
    Status,
    crunch,
    discover,
    limited_dimensions,
    resolve_max_pixels,
    run,
)
from image_crunch.core import build_candidate
from PIL import Image, PngImagePlugin


class CrunchTests(unittest.TestCase):
    def test_exact_pixel_and_named_resolution_limits(self):
        self.assertEqual(resolve_max_pixels(2_073_600), 2_073_600)
        self.assertEqual(
            resolve_max_pixels(ResolutionPreset.FULL_HD_1080P), 1920 * 1080
        )
        self.assertEqual(limited_dimensions(1000, 800, 1_000_000), (1000, 800))
        width, height = limited_dimensions(4000, 3000, 2_000_000)
        self.assertLessEqual(width * height, 2_000_000)
        self.assertAlmostEqual(width / height, 4 / 3, places=2)

    def test_invalid_pixel_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_max_pixels(0)

    def test_discovery_respects_recursion_and_patterns(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            direct = root / "direct.png"
            nested = root / "nested" / "nested.webp"
            nested.parent.mkdir()
            direct.touch()
            nested.touch()
            self.assertEqual(
                discover([root], recursive=False, patterns=("*.png", "*.webp")),
                [direct],
            )
            self.assertEqual(
                discover([root], recursive=True, patterns=("*.png", "*.webp")),
                [direct, nested],
            )

    @patch("image_crunch.core.build_candidate")
    def test_candidate_must_meet_maximum_size_ratio(self, build_candidate):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "image.png"
            source.write_bytes(b"x" * 100)
            build_candidate.side_effect = lambda _source, candidate, **_options: (
                candidate.write_bytes(b"y" * 91)
            )

            kept = crunch(
                source,
                transform=Transform(),
                encode=EncodeOptions(),
                max_size_ratio=0.9,
            )
            self.assertEqual(kept.status, Status.KEPT)
            self.assertTrue(source.exists())

            build_candidate.side_effect = lambda _source, candidate, **_options: (
                candidate.write_bytes(b"y" * 80)
            )
            replaced = crunch(
                source,
                transform=Transform(),
                encode=EncodeOptions(),
                max_size_ratio=0.9,
            )
            self.assertEqual(replaced.status, Status.REPLACED)
            self.assertFalse(source.exists())
            self.assertEqual(source.with_suffix(".webp").stat().st_size, 80)

    def test_preset_defaults_and_cli_overrides_are_owned_by_shared_runner(self):
        preset = ImageCrunchPreset(
            "test-crunch",
            "Test",
            encode=EncodeOptions(webp_quality=88, webp_method=5),
        )
        with tempfile.TemporaryDirectory() as directory:
            empty = Path(directory)
            self.assertEqual(run(preset, [str(empty)]), 2)

    @patch("image_crunch.cli.crunch")
    @patch("image_crunch.cli.discover")
    def test_cli_accepts_exact_max_pixels(self, discover, crunch_image):
        source = Path("image.png")
        discover.return_value = [source]
        crunch_image.return_value = Mock(
            status=Status.KEPT,
            source=source,
            destination=Path("image.webp"),
            original_size=100,
            candidate_size=90,
        )
        preset = ImageCrunchPreset("test-crunch", "Test")
        self.assertEqual(run(preset, ["image.png", "--max-pixels", "2073600"]), 0)
        self.assertEqual(crunch_image.call_args.kwargs["max_pixels"], 2_073_600)


class ImagePipelineTests(unittest.TestCase):
    def test_pixel_limit_downscales_only_when_needed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            large = root / "large.png"
            large_output = root / "large.webp"
            small = root / "small.png"
            small_output = root / "small.webp"
            Image.new("RGB", (2000, 1000)).save(large)
            Image.new("RGB", (800, 600)).save(small)

            build_candidate(
                large,
                large_output,
                transform=Transform(),
                encode=EncodeOptions(),
                max_pixels=1_000_000,
            )
            build_candidate(
                small,
                small_output,
                transform=Transform(),
                encode=EncodeOptions(),
                max_pixels=1_000_000,
            )

            with Image.open(large_output) as result:
                self.assertLessEqual(result.width * result.height, 1_000_000)
                self.assertAlmostEqual(result.width / result.height, 2.0, places=2)
            with Image.open(small_output) as result:
                self.assertEqual(result.size, (800, 600))

    def test_png_to_webp_preserves_comfyui_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "image.png"
            destination = root / "image.webp"
            randomizer = random.Random(7)
            image = Image.new("RGB", (32, 32))
            image.putdata(
                [
                    tuple(randomizer.randrange(256) for _ in range(3))
                    for _ in range(32 * 32)
                ]
            )
            expected = Metadata(
                {"nodes": [{"type": "KSampler"}]}, {"1": {"class_type": "KSampler"}}
            )
            info = PngImagePlugin.PngInfo()
            info.add_text("workflow", json.dumps(expected.workflow))
            info.add_text("prompt", json.dumps(expected.prompt))
            image.save(source, pnginfo=info)

            convert_to_webp(
                source,
                destination,
                encode_options=EncodeOptions(webp_quality=90, webp_method=6),
                webp_exif=metadata_for_webp(read_metadata(source)),
            )

            self.assertEqual(read_metadata(destination), expected)


if __name__ == "__main__":
    unittest.main()
