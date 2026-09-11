import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from image_convert import (
    Animation,
    AnimationFrame,
    AnimationToStillError,
    EncodeOptions,
    InvalidEncodeOptionError,
    OutputFormat,
    OutputVerificationError,
    StillImage,
    Transform,
    add_image_conversion_arguments,
    convert_transactionally,
    decode,
    encode,
    image_conversion_arguments,
    transform,
    validate_encode_options,
)
from PIL import Image, features


def still() -> StillImage:
    return StillImage(Image.new("RGBA", (3, 2), (20, 40, 60, 255)))


def animation() -> Animation:
    return Animation(
        width=2,
        height=2,
        loop_count=3,
        frames=(
            AnimationFrame(Image.new("RGBA", (2, 2), (255, 0, 0, 255)), 100),
            AnimationFrame(Image.new("RGBA", (2, 2), (0, 0, 255, 255)), 200),
        ),
    )


class StillImageTests(unittest.TestCase):
    def test_supported_still_outputs_and_resize(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for format_, name in (
                (OutputFormat.PNG, "image.png"),
                (OutputFormat.JPEG, "image.jpg"),
                (OutputFormat.WEBP, "image.webp"),
                (OutputFormat.GIF, "image.gif"),
            ):
                path = root / name
                encode(path, still(), format_)
                decoded = decode(path)
                self.assertIsInstance(decoded, StillImage)
                self.assertEqual(decoded.dimensions, (3, 2))

        resized = transform(still(), Transform(width=6))
        self.assertEqual(resized.dimensions, (6, 4))

    def test_bmp_and_tiff_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, format_ in (("input.bmp", "BMP"), ("input.tiff", "TIFF")):
                path = Path(directory) / name
                Image.new("RGB", (4, 3), "purple").save(path, format=format_)
                self.assertEqual(decode(path).dimensions, (4, 3))

    def test_still_webp_is_not_decoded_as_animation(self):
        if not features.check("webp"):
            self.fail("Pillow was installed without WebP support")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "still.webp"
            encode(path, still(), OutputFormat.WEBP)
            self.assertIsInstance(decode(path), StillImage)


class AnimationTests(unittest.TestCase):
    def test_gif_webp_gif_preserves_animation_shape_timing_and_loop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gif = root / "animation.gif"
            encode(gif, animation(), OutputFormat.GIF)
            decoded_gif = decode(gif)
            self.assertIsInstance(decoded_gif, Animation)
            self.assertEqual(len(decoded_gif.frames), 2)
            self.assertEqual(decoded_gif.loop_count, 3)
            self.assertEqual(
                [frame.duration_ms for frame in decoded_gif.frames], [100, 200]
            )

            webp = root / "animation.webp"
            encode(
                webp, decoded_gif, OutputFormat.WEBP, EncodeOptions(webp_lossless=True)
            )
            decoded_webp = decode(webp)
            self.assertIsInstance(decoded_webp, Animation)
            self.assertEqual(len(decoded_webp.frames), 2)
            self.assertEqual(decoded_webp.loop_count, 3)
            self.assertEqual(
                [frame.duration_ms for frame in decoded_webp.frames], [100, 200]
            )

            second_gif = root / "roundtrip.gif"
            encode(second_gif, decoded_webp, OutputFormat.GIF)
            self.assertIsInstance(decode(second_gif), Animation)

    def test_transform_applies_to_every_frame(self):
        transformed = transform(animation(), Transform(width=4, rotate=90))
        self.assertIsInstance(transformed, Animation)
        self.assertEqual(transformed.dimensions, (4, 4))
        self.assertTrue(all(frame.image.size == (4, 4) for frame in transformed.frames))
        self.assertEqual(
            [frame.duration_ms for frame in transformed.frames], [100, 200]
        )

    def test_animation_to_still_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(AnimationToStillError):
                encode(Path(directory) / "animation.png", animation(), OutputFormat.PNG)


class SafetyAndValidationTests(unittest.TestCase):
    def test_irrelevant_codec_option_is_rejected(self):
        with self.assertRaisesRegex(InvalidEncodeOptionError, "WebP"):
            validate_encode_options(
                OutputFormat.JPEG, EncodeOptions(webp_lossless=True)
            )

    def test_same_input_and_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.png"
            encode(path, still(), OutputFormat.PNG)
            with self.assertRaisesRegex(ValueError, "must be different"):
                convert_transactionally(path, path, overwrite=True)

    def test_verification_failure_preserves_existing_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            destination = root / "destination.png"
            encode(source, still(), OutputFormat.PNG)
            destination.write_bytes(b"original destination")
            with (
                patch(
                    "image_convert.core.verify_output",
                    side_effect=OutputVerificationError("forced verification failure"),
                ),
                self.assertRaisesRegex(OutputVerificationError, "forced"),
            ):
                convert_transactionally(source, destination, overwrite=True)
            self.assertEqual(destination.read_bytes(), b"original destination")
            self.assertEqual(
                sorted(path.name for path in root.iterdir()),
                ["destination.png", "source.png"],
            )


class ArgumentCompositionTests(unittest.TestCase):
    def test_conversion_arguments_stack_onto_a_caller_owned_parser(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--profile")
        add_image_conversion_arguments(
            parser,
            output_format=OutputFormat.WEBP,
            encode_defaults=EncodeOptions(webp_quality=90, webp_method=6),
        )

        namespace = parser.parse_args(
            ["--profile", "ai", "--width", "800", "--webp-quality", "82"]
        )
        options = image_conversion_arguments(namespace)

        self.assertEqual(namespace.profile, "ai")
        self.assertEqual(options.transform, Transform(width=800))
        self.assertEqual(options.encode, EncodeOptions(webp_quality=82, webp_method=6))
        self.assertNotIn("--jpeg-quality", parser.format_help())


if __name__ == "__main__":
    unittest.main()
