from __future__ import annotations

import argparse
import sys
from pathlib import Path

from video_transcode.cli import main as transcode_main

from .core import (
    Status,
    VideoCrunchPreset,
    crunch,
    destination_collisions,
    destination_for,
    discover,
)


def _ratio(value: str) -> float:
    ratio = float(value)
    if not 0 < ratio <= 1:
        raise argparse.ArgumentTypeError("must be greater than 0 and at most 1")
    return ratio


def _parser(preset: VideoCrunchPreset) -> argparse.ArgumentParser:
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
        "--max-size-ratio",
        type=_ratio,
        default=preset.max_size_ratio,
        metavar="RATIO",
        help="replace only when candidate size / original size is at most RATIO (default: %(default)s)",
    )
    return parser


def run(preset: VideoCrunchPreset, argv: list[str] | None = None) -> int:
    arguments = _parser(preset).parse_args(argv)
    paths = tuple(path.expanduser() for path in arguments.paths)
    patterns = tuple(arguments.patterns or preset.patterns)
    try:
        sources = discover(paths, recursive=arguments.recursive, patterns=patterns)
    except FileNotFoundError as error:
        print(f"{preset.command}: {error}", file=sys.stderr)
        return 2
    if not sources:
        print(f"{preset.command}: no matching videos found", file=sys.stderr)
        return 2
    collisions = destination_collisions(sources, preset.output_suffix)
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

    failures = 0
    for index, source in enumerate(sources, start=1):
        if len(sources) > 1:
            print(f"\n[{index}/{len(sources)}]")
        destination = destination_for(source, preset.output_suffix)
        print(f"\n=== {source} -> {destination} ===\n")

        def transcode(input_path: Path, candidate: Path) -> int:
            return transcode_main(
                [str(input_path), str(candidate), *preset.transcode_arguments]
            )

        result = crunch(
            source,
            transcode,
            max_size_ratio=arguments.max_size_ratio,
            output_suffix=preset.output_suffix,
        )
        if result.status is Status.FAILED:
            failures += 1
            print(f"{preset.command}: transcode failed: {source}", file=sys.stderr)
        elif result.status is Status.KEPT:
            ratio = (
                result.candidate_size / result.original_size
                if result.original_size
                else float("inf")
            )
            print(
                f"Kept original: candidate was {ratio:.1%}; required {arguments.max_size_ratio:.1%} or less."
            )
        else:
            print(f"Replaced original: saved {result.reduction_ratio:.1%}.")
    if failures:
        print(
            f"{preset.command}: {failures} of {len(sources)} transcodes failed",
            file=sys.stderr,
        )
        return 1
    return 0
