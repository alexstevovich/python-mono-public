from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PIL import Image, ImageSequence, UnidentifiedImageError

from .errors import (
    AnimationToStillError,
    InvalidEncodeOptionError,
    InvalidTransformError,
    OutputVerificationError,
    UnsupportedInputError,
    UnsupportedOutputError,
)

SUPPORTED_INPUTS = {"PNG", "JPEG", "WEBP", "BMP", "TIFF", "GIF"}


class OutputFormat(Enum):
    PNG = "PNG"
    JPEG = "JPEG"
    WEBP = "WEBP"
    GIF = "GIF"

    @classmethod
    def from_path(cls, path: str | os.PathLike[str]) -> OutputFormat:
        suffix = Path(path).suffix.lower()
        formats = {
            ".png": cls.PNG,
            ".jpg": cls.JPEG,
            ".jpeg": cls.JPEG,
            ".webp": cls.WEBP,
            ".gif": cls.GIF,
        }
        try:
            return formats[suffix]
        except KeyError as error:
            raise UnsupportedOutputError() from error


@dataclass(frozen=True)
class AnimationFrame:
    image: Image.Image
    duration_ms: int


@dataclass(frozen=True)
class StillImage:
    image: Image.Image

    @property
    def dimensions(self) -> tuple[int, int]:
        return self.image.size


@dataclass(frozen=True)
class Animation:
    width: int
    height: int
    frames: tuple[AnimationFrame, ...]
    loop_count: int = 0

    @property
    def dimensions(self) -> tuple[int, int]:
        return self.width, self.height


ImageAsset = StillImage | Animation


@dataclass(frozen=True)
class Transform:
    width: int | None = None
    height: int | None = None
    crop: tuple[int, int, int, int] | None = None
    rotate: int = 0


@dataclass(frozen=True)
class EncodeOptions:
    jpeg_quality: int | None = None
    webp_quality: float | None = None
    webp_lossless: bool = False
    webp_method: int | None = None
    png_compression: int | None = None


def decode(path: str | os.PathLike[str]) -> ImageAsset:
    try:
        with Image.open(path) as source:
            if source.format not in SUPPORTED_INPUTS:
                raise UnsupportedInputError()
            frame_count = getattr(source, "n_frames", 1)
            if source.format in {"GIF", "WEBP"} and frame_count > 1:
                minimum_duration = 10 if source.format == "GIF" else 1
                frames = tuple(
                    AnimationFrame(
                        image=frame.convert("RGBA").copy(),
                        duration_ms=max(
                            int(
                                frame.info.get(
                                    "duration", source.info.get("duration", 0)
                                )
                            ),
                            minimum_duration,
                        ),
                    )
                    for frame in ImageSequence.Iterator(source)
                )
                return Animation(
                    width=source.width,
                    height=source.height,
                    frames=frames,
                    loop_count=int(source.info.get("loop", 0)),
                )
            return StillImage(source.convert("RGBA").copy())
    except (UnidentifiedImageError, OSError) as error:
        raise UnsupportedInputError() from error


def _apply(image: Image.Image, options: Transform) -> Image.Image:
    result = image
    if options.crop is not None:
        x, y, width, height = options.crop
        if width <= 0 or height <= 0 or x < 0 or y < 0:
            raise InvalidTransformError("crop lies outside the image")
        if x + width > result.width or y + height > result.height:
            raise InvalidTransformError("crop lies outside the image")
        result = result.crop((x, y, x + width, y + height))

    if options.width is not None or options.height is not None:
        original_width, original_height = result.size
        if options.width is not None and options.height is not None:
            width, height = options.width, options.height
        elif options.width is not None:
            width = options.width
            height = original_height * width // original_width
        else:
            assert options.height is not None
            height = options.height
            width = original_width * height // original_height
        if width <= 0 or height <= 0:
            raise InvalidTransformError("dimensions must be nonzero")
        result = result.resize((width, height), Image.Resampling.LANCZOS)

    rotations = {
        0: None,
        90: Image.Transpose.ROTATE_270,
        180: Image.Transpose.ROTATE_180,
        270: Image.Transpose.ROTATE_90,
    }
    if options.rotate not in rotations:
        raise InvalidTransformError("rotation must be 0, 90, 180, or 270")
    transpose = rotations[options.rotate]
    return result.copy() if transpose is None else result.transpose(transpose)


def transform(asset: ImageAsset, options: Transform) -> ImageAsset:
    if isinstance(asset, StillImage):
        return StillImage(_apply(asset.image, options))
    frames = tuple(
        AnimationFrame(_apply(frame.image, options), frame.duration_ms)
        for frame in asset.frames
    )
    if not frames:
        raise InvalidTransformError("animation contains no frames")
    width, height = frames[0].image.size
    return Animation(width, height, frames, asset.loop_count)


def validate_encode_options(format_: OutputFormat, options: EncodeOptions) -> None:
    if options.jpeg_quality is not None:
        if format_ is not OutputFormat.JPEG:
            raise InvalidEncodeOptionError("jpeg_quality applies only to JPEG output")
        if not 1 <= options.jpeg_quality <= 100:
            raise InvalidEncodeOptionError("jpeg_quality must be between 1 and 100")
    if (
        options.webp_quality is not None
        or options.webp_lossless
        or options.webp_method is not None
    ):
        if format_ is not OutputFormat.WEBP:
            raise InvalidEncodeOptionError("WebP options apply only to WebP output")
    if options.webp_quality is not None and not 0 <= options.webp_quality <= 100:
        raise InvalidEncodeOptionError("webp_quality must be between 0 and 100")
    if options.webp_method is not None and not 0 <= options.webp_method <= 6:
        raise InvalidEncodeOptionError("webp_method must be between 0 and 6")
    if options.png_compression is not None:
        if format_ is not OutputFormat.PNG:
            raise InvalidEncodeOptionError("png_compression applies only to PNG output")
        if not 0 <= options.png_compression <= 9:
            raise InvalidEncodeOptionError("png_compression must be between 0 and 9")


def _save_still(
    path: Path,
    asset: StillImage,
    format_: OutputFormat,
    options: EncodeOptions,
    webp_exif: bytes | None = None,
) -> None:
    image = asset.image
    if format_ is OutputFormat.JPEG:
        image.convert("RGB").save(
            path, format="JPEG", quality=options.jpeg_quality or 85
        )
    elif format_ is OutputFormat.PNG:
        arguments = (
            {}
            if options.png_compression is None
            else {"compress_level": options.png_compression}
        )
        image.save(path, format="PNG", **arguments)
    elif format_ is OutputFormat.WEBP:
        metadata = {} if webp_exif is None else {"exif": webp_exif}
        image.save(
            path,
            format="WEBP",
            quality=options.webp_quality
            if options.webp_quality is not None
            else (75 if options.webp_lossless else 85),
            lossless=options.webp_lossless,
            method=options.webp_method if options.webp_method is not None else 4,
            **metadata,
        )
    else:
        image.save(path, format="GIF")


def _save_animation(
    path: Path,
    asset: Animation,
    format_: OutputFormat,
    options: EncodeOptions,
    webp_exif: bytes | None = None,
) -> None:
    if format_ in {OutputFormat.PNG, OutputFormat.JPEG}:
        raise AnimationToStillError()
    first, *remaining = [frame.image for frame in asset.frames]
    durations = [frame.duration_ms for frame in asset.frames]
    if format_ is OutputFormat.GIF:
        first.save(
            path,
            format="GIF",
            save_all=True,
            append_images=remaining,
            duration=durations,
            loop=asset.loop_count,
            disposal=2,
        )
    else:
        metadata = {} if webp_exif is None else {"exif": webp_exif}
        first.save(
            path,
            format="WEBP",
            save_all=True,
            append_images=remaining,
            duration=durations,
            loop=asset.loop_count,
            quality=options.webp_quality
            if options.webp_quality is not None
            else (75 if options.webp_lossless else 85),
            lossless=options.webp_lossless,
            method=options.webp_method if options.webp_method is not None else 4,
            **metadata,
        )


def encode(
    path: str | os.PathLike[str],
    asset: ImageAsset,
    format_: OutputFormat,
    options: EncodeOptions | None = None,
    *,
    webp_exif: bytes | None = None,
) -> None:
    encode_options = options or EncodeOptions()
    validate_encode_options(format_, encode_options)
    destination = Path(path)
    if webp_exif is not None and format_ is not OutputFormat.WEBP:
        raise InvalidEncodeOptionError("webp_exif applies only to WebP output")
    if isinstance(asset, Animation):
        _save_animation(destination, asset, format_, encode_options, webp_exif)
    else:
        _save_still(destination, asset, format_, encode_options, webp_exif)


def convert_image(
    source: str | os.PathLike[str],
    destination: str | os.PathLike[str],
    *,
    transform_options: Transform | None = None,
    encode_options: EncodeOptions | None = None,
    overwrite: bool = False,
    webp_exif: bytes | None = None,
) -> None:
    convert_transactionally(
        source,
        destination,
        transform_options=transform_options,
        encode_options=encode_options,
        overwrite=overwrite,
        webp_exif=webp_exif,
    )


def asset_dimensions(asset: ImageAsset) -> tuple[int, int]:
    return asset.dimensions


def verify_output(path: str | os.PathLike[str], expected: ImageAsset) -> None:
    actual = decode(path)
    if asset_dimensions(actual) != asset_dimensions(expected):
        raise OutputVerificationError(
            "output verification failed: image dimensions differ"
        )
    if isinstance(expected, Animation):
        if not isinstance(actual, Animation):
            raise OutputVerificationError(
                "output verification failed: animation was not preserved"
            )
        if len(actual.frames) != len(expected.frames):
            raise OutputVerificationError(
                "output verification failed: animation frame count differs"
            )


def convert_transactionally(
    source: str | os.PathLike[str],
    destination: str | os.PathLike[str],
    *,
    transform_options: Transform | None = None,
    encode_options: EncodeOptions | None = None,
    overwrite: bool = False,
    webp_exif: bytes | None = None,
) -> None:
    source_path = Path(source)
    destination_path = Path(destination)
    parent = (
        destination_path.parent if destination_path.parent != Path("") else Path(".")
    )
    resolved_source = source_path.resolve(strict=True)
    resolved_parent = parent.resolve(strict=True)
    resolved_destination = (
        destination_path.resolve(strict=True)
        if destination_path.exists()
        else resolved_parent / destination_path.name
    )
    if resolved_source == resolved_destination:
        raise ValueError(
            "input and output must be different; the source is never overwritten"
        )
    if destination_path.exists() and not overwrite:
        raise FileExistsError(
            f"output already exists: {destination_path} (use overwrite=True to replace it)"
        )
    format_ = OutputFormat.from_path(destination_path)
    asset = transform(decode(source_path), transform_options or Transform())
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".image-convert-", suffix=".tmp", dir=parent
    )
    os.close(descriptor)
    candidate = Path(temporary_name)
    try:
        encode(candidate, asset, format_, encode_options, webp_exif=webp_exif)
        verify_output(candidate, asset)
        os.replace(candidate, destination_path)
    except BaseException:
        candidate.unlink(missing_ok=True)
        raise


def convert_to_webp(
    source: str | os.PathLike[str],
    destination: str | os.PathLike[str],
    *,
    transform_options: Transform | None = None,
    encode_options: EncodeOptions | None = None,
    webp_exif: bytes | None = None,
) -> None:
    """Convenience adapter for callers whose output is always WebP."""
    if Path(destination).suffix.lower() != ".webp":
        raise UnsupportedOutputError()
    convert_transactionally(
        source,
        destination,
        transform_options=transform_options,
        encode_options=encode_options,
        overwrite=True,
        webp_exif=webp_exif,
    )
