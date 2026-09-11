from __future__ import annotations

import math
import os
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from comfyui_metadata import metadata_for_webp, read_metadata
from image_convert import EncodeOptions, Transform, convert_to_webp
from PIL import Image


class Status(Enum):
    REPLACED = "replaced"
    KEPT = "kept"
    FAILED = "failed"


class ResolutionPreset(Enum):
    """Common display tiers usable as exact image-crunch pixel ceilings."""

    HD_720P = (1280, 720)
    FULL_HD_1080P = (1920, 1080)
    QHD_1440P = (2560, 1440)
    UHD_4K = (3840, 2160)

    @property
    def max_pixels(self) -> int:
        width, height = self.value
        return width * height


@dataclass(frozen=True)
class ImageCrunchPreset:
    command: str
    description: str
    patterns: tuple[str, ...] = ("*.png", "*.webp")
    max_size_ratio: float = 0.9
    max_pixels: int | ResolutionPreset | None = None
    encode: EncodeOptions = EncodeOptions()
    transform: Transform = Transform()


@dataclass(frozen=True)
class CrunchResult:
    source: Path
    destination: Path
    status: Status
    original_size: int
    candidate_size: int | None = None
    error: str | None = None


CandidateBuilder = Callable[[Path, Path], None]


def resolve_max_pixels(limit: int | ResolutionPreset | None) -> int | None:
    """Resolve a literal pixel ceiling or an exact named display tier."""
    if limit is None:
        return None
    if isinstance(limit, ResolutionPreset):
        return limit.max_pixels
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("max_pixels must be a positive integer")
    return limit


def limited_dimensions(
    width: int,
    height: int,
    limit: int | ResolutionPreset | None,
) -> tuple[int, int]:
    pixels = resolve_max_pixels(limit)
    if pixels is None or width * height <= pixels:
        return width, height
    scale = math.sqrt(pixels / (width * height))
    return max(1, int(width * scale)), max(1, int(height * scale))


def _limited_transform(
    source: Path,
    transform: Transform,
    max_pixels: int | ResolutionPreset | None,
) -> Transform:
    if max_pixels is None:
        return transform
    if transform.width is not None or transform.height is not None:
        raise ValueError("max_pixels cannot be combined with explicit width or height")
    with Image.open(source) as image:
        width, height = image.size
    if transform.crop is not None:
        _, _, width, height = transform.crop
    limited_width, limited_height = limited_dimensions(width, height, max_pixels)
    if (limited_width, limited_height) == (width, height):
        return transform
    return Transform(
        width=limited_width,
        height=limited_height,
        crop=transform.crop,
        rotate=transform.rotate,
    )


def discover(
    paths: Iterable[Path], *, recursive: bool, patterns: tuple[str, ...]
) -> list[Path]:
    found: dict[str, Path] = {}
    for path in paths:
        if path.is_file():
            candidates = [path]
        elif path.is_dir():
            candidates = path.rglob("*") if recursive else path.glob("*")
        else:
            raise FileNotFoundError(f"path does not exist: {path}")
        for candidate in candidates:
            if candidate.is_file() and any(
                candidate.match(pattern) for pattern in patterns
            ):
                found.setdefault(str(candidate.resolve()).casefold(), candidate)
    return sorted(found.values(), key=lambda item: str(item).casefold())


def destination_for(source: Path) -> Path:
    return source.with_suffix(".webp")


def destination_collisions(sources: Iterable[Path]) -> dict[Path, list[Path]]:
    destinations: dict[Path, list[Path]] = {}
    for source in sources:
        destinations.setdefault(destination_for(source).resolve(), []).append(source)
    return {
        destination: inputs
        for destination, inputs in destinations.items()
        if len(inputs) > 1
    }


def build_candidate(
    source: Path,
    candidate: Path,
    *,
    transform: Transform,
    encode: EncodeOptions,
    max_pixels: int | ResolutionPreset | None = None,
) -> None:
    metadata = read_metadata(source)
    convert_to_webp(
        source,
        candidate,
        transform_options=_limited_transform(source, transform, max_pixels),
        encode_options=encode,
        webp_exif=metadata_for_webp(metadata),
    )
    if read_metadata(candidate) != metadata:
        raise ValueError("ComfyUI metadata verification failed")


def crunch(
    source: Path,
    *,
    transform: Transform,
    encode: EncodeOptions,
    max_size_ratio: float,
    max_pixels: int | ResolutionPreset | None = None,
) -> CrunchResult:
    if not 0 < max_size_ratio <= 1:
        raise ValueError("max_size_ratio must be greater than 0 and at most 1")
    destination = destination_for(source)
    original_size = source.stat().st_size
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".crunch-",
        suffix=destination.suffix,
        dir=destination.parent,
    )
    os.close(descriptor)
    candidate = Path(temporary_name)
    try:
        try:
            build_candidate(
                source,
                candidate,
                transform=transform,
                encode=encode,
                max_pixels=max_pixels,
            )
            candidate_size = candidate.stat().st_size
        except (OSError, ValueError) as error:
            return CrunchResult(
                source, destination, Status.FAILED, original_size, error=str(error)
            )
        if candidate_size > original_size * max_size_ratio:
            return CrunchResult(
                source, destination, Status.KEPT, original_size, candidate_size
            )
        os.replace(candidate, destination)
        if source.resolve() != destination.resolve():
            source.unlink()
        return CrunchResult(
            source, destination, Status.REPLACED, original_size, candidate_size
        )
    finally:
        candidate.unlink(missing_ok=True)
