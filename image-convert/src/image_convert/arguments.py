from __future__ import annotations

import argparse
from dataclasses import dataclass

from .core import EncodeOptions, OutputFormat, Transform


@dataclass(frozen=True)
class ImageConversionArguments:
    transform: Transform
    encode: EncodeOptions


def add_transform_arguments(
    parser: argparse.ArgumentParser,
    *,
    defaults: Transform | None = None,
) -> None:
    values = defaults or Transform()
    group = parser.add_argument_group("image transform")
    group.add_argument("--width", type=int, default=values.width)
    group.add_argument("--height", type=int, default=values.height)
    group.add_argument(
        "--crop",
        type=int,
        nargs=4,
        metavar=("X", "Y", "WIDTH", "HEIGHT"),
        default=values.crop,
    )
    group.add_argument(
        "--rotate", type=int, choices=(0, 90, 180, 270), default=values.rotate
    )


def add_encode_arguments(
    parser: argparse.ArgumentParser,
    *,
    output_format: OutputFormat | None = None,
    defaults: EncodeOptions | None = None,
) -> None:
    values = defaults or EncodeOptions()
    group = parser.add_argument_group("image encoding")
    if output_format in {None, OutputFormat.JPEG}:
        group.add_argument("--jpeg-quality", type=int, default=values.jpeg_quality)
    if output_format in {None, OutputFormat.WEBP}:
        group.add_argument("--webp-quality", type=float, default=values.webp_quality)
        group.add_argument(
            "--webp-lossless", action="store_true", default=values.webp_lossless
        )
        group.add_argument(
            "--webp-method", type=int, choices=range(7), default=values.webp_method
        )
    if output_format in {None, OutputFormat.PNG}:
        group.add_argument(
            "--png-compression",
            type=int,
            choices=range(10),
            default=values.png_compression,
        )


def add_image_conversion_arguments(
    parser: argparse.ArgumentParser,
    *,
    output_format: OutputFormat | None = None,
    transform_defaults: Transform | None = None,
    encode_defaults: EncodeOptions | None = None,
) -> None:
    add_transform_arguments(parser, defaults=transform_defaults)
    add_encode_arguments(parser, output_format=output_format, defaults=encode_defaults)


def image_conversion_arguments(
    namespace: argparse.Namespace,
) -> ImageConversionArguments:
    return ImageConversionArguments(
        transform=Transform(
            width=getattr(namespace, "width", None),
            height=getattr(namespace, "height", None),
            crop=tuple(namespace.crop) if getattr(namespace, "crop", None) else None,
            rotate=getattr(namespace, "rotate", 0),
        ),
        encode=EncodeOptions(
            jpeg_quality=getattr(namespace, "jpeg_quality", None),
            webp_quality=getattr(namespace, "webp_quality", None),
            webp_lossless=getattr(namespace, "webp_lossless", False),
            webp_method=getattr(namespace, "webp_method", None),
            png_compression=getattr(namespace, "png_compression", None),
        ),
    )
