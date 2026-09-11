from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

DEFAULT_VIDEO_PATTERNS = (
    "*.avi",
    "*.flv",
    "*.m2ts",
    "*.m4v",
    "*.mkv",
    "*.mov",
    "*.mp4",
    "*.mpeg",
    "*.mpg",
    "*.mts",
    "*.ts",
    "*.webm",
    "*.wmv",
)


class Status(Enum):
    REPLACED = "replaced"
    KEPT = "kept"
    FAILED = "failed"


@dataclass(frozen=True)
class VideoCrunchPreset:
    command: str
    description: str
    transcode_arguments: tuple[str, ...]
    patterns: tuple[str, ...] = DEFAULT_VIDEO_PATTERNS
    max_size_ratio: float = 0.9
    output_suffix: str = ".mkv"


@dataclass(frozen=True)
class CrunchResult:
    source: Path
    destination: Path
    status: Status
    original_size: int
    candidate_size: int | None = None
    transcode_returncode: int = 0

    @property
    def reduction_ratio(self) -> float | None:
        if self.candidate_size is None or self.original_size == 0:
            return None
        return 1 - self.candidate_size / self.original_size


Transcode = Callable[[Path, Path], int]


def destination_for(source: Path, suffix: str) -> Path:
    return source.with_suffix(suffix)


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


def destination_collisions(
    sources: Iterable[Path], suffix: str
) -> dict[Path, list[Path]]:
    grouped: dict[Path, list[Path]] = {}
    for source in sources:
        grouped.setdefault(destination_for(source, suffix).resolve(), []).append(source)
    return {
        destination: inputs
        for destination, inputs in grouped.items()
        if len(inputs) > 1
    }


def crunch(
    source: Path,
    transcode: Transcode,
    *,
    max_size_ratio: float,
    output_suffix: str,
) -> CrunchResult:
    if not 0 < max_size_ratio <= 1:
        raise ValueError("max_size_ratio must be greater than 0 and at most 1")
    destination = destination_for(source, output_suffix)
    original_size = source.stat().st_size
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".video-crunch-",
        suffix=output_suffix,
        dir=source.parent,
    )
    os.close(descriptor)
    candidate = Path(temporary_name)
    candidate.unlink()
    try:
        returncode = transcode(source, candidate)
        if returncode != 0 or not candidate.is_file() or candidate.stat().st_size == 0:
            return CrunchResult(
                source,
                destination,
                Status.FAILED,
                original_size,
                transcode_returncode=returncode or 1,
            )
        candidate_size = candidate.stat().st_size
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
