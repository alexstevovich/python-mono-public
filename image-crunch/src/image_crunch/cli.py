from __future__ import annotations

import argparse
import sys
from pathlib import Path

from image_convert import EncodeOptions

from .core import ImageCrunchPreset, Status, crunch, destination_collisions, discover


def _ratio(value: str) -> float:
    ratio = float(value)
    if not 0 < ratio <= 1:
        raise argparse.ArgumentTypeError("must be greater than 0 and at most 1")
    return ratio


def _positive_pixels(value: str) -> int:
    pixels = int(value)
    if pixels <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return pixels


def _parser(preset: ImageCrunchPreset) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=preset.command, description=preset.description
    )
    parser.add_argument("paths", nargs="+", type=Path, metavar="PATH")
    selection = parser.add_argument_group("file selection and replacement")
    selection.add_argument(
        "--recursive", action="store_true", help="search inside subdirectories"
    )
    selection.add_argument(
        "--pattern",
        action="append",
        dest="patterns",
        metavar="GLOB",
        help=f"filename pattern; repeat as needed (default: {', '.join(preset.patterns)})",
    )
    selection.add_argument(
        "--max-pixels",
        type=_positive_pixels,
        default=preset.max_pixels,
        metavar="PIXELS",
        help="downscale images exceeding this exact width x height pixel count",
    )
    selection.add_argument(
        "--max-size-ratio",
        type=_ratio,
        default=preset.max_size_ratio,
        metavar="RATIO",
        help="replace only when candidate size / original size is at most RATIO (default: %(default)s)",
    )
    conversion = parser.add_argument_group("WebP conversion")
    conversion.add_argument("--quality", type=float, default=preset.encode.webp_quality)
    conversion.add_argument(
        "--method", type=int, choices=range(7), default=preset.encode.webp_method
    )
    conversion.add_argument(
        "--lossless", action="store_true", default=preset.encode.webp_lossless
    )
    return parser


def run(preset: ImageCrunchPreset, argv: list[str] | None = None) -> int:
    arguments = _parser(preset).parse_args(argv)
    paths = tuple(path.expanduser() for path in arguments.paths)
    patterns = tuple(arguments.patterns or preset.patterns)
    try:
        sources = discover(paths, recursive=arguments.recursive, patterns=patterns)
    except FileNotFoundError as error:
        print(f"{preset.command}: {error}", file=sys.stderr)
        return 2
    if not sources:
        print(f"{preset.command}: no matching images found", file=sys.stderr)
        return 2

    collisions = destination_collisions(sources)
    if collisions:
        print(
            f"{preset.command}: multiple inputs map to the same output:",
            file=sys.stderr,
        )
        for destination, inputs in collisions.items():
            print(f"  {destination}", file=sys.stderr)
            for source in inputs:
                print(f"    <- {source}", file=sys.stderr)
        return 2

    encode = EncodeOptions(
        webp_quality=arguments.quality,
        webp_lossless=arguments.lossless,
        webp_method=arguments.method,
    )
    transform = preset.transform
    failures = 0
    for source in sources:
        result = crunch(
            source,
            transform=transform,
            encode=encode,
            max_size_ratio=arguments.max_size_ratio,
            max_pixels=arguments.max_pixels,
        )
        if result.status is Status.FAILED:
            failures += 1
            print(f"FAILED  {source}: {result.error}", file=sys.stderr)
        elif result.status is Status.KEPT:
            ratio = (
                result.candidate_size / result.original_size
                if result.original_size
                else float("inf")
            )
            print(f"KEPT    {source} (candidate {ratio:.1%} of original)")
        else:
            saved = (
                1 - result.candidate_size / result.original_size
                if result.original_size
                else 0
            )
            print(f"CRUNCHED {source} -> {result.destination} (saved {saved:.1%})")
    return 1 if failures else 0
