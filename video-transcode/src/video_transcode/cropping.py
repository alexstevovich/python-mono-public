from __future__ import annotations

import math
import re
import subprocess
from collections import Counter
from pathlib import Path

from .errors import ProbeError
from .models import CropAnalysis, CropRect, MediaInfo

CROP_PATTERN = re.compile(r"\bcrop=(\d+):(\d+):(\d+):(\d+)\b")


def sample_positions(duration: float | None, count: int = 5) -> tuple[float, ...]:
    if not duration or duration <= 0:
        return (0.0,)
    return tuple(
        duration * fraction for fraction in (0.10, 0.30, 0.50, 0.70, 0.90)[:count]
    )


def parse_crop_candidates(stderr: str) -> tuple[CropRect, ...]:
    return tuple(
        CropRect(*(int(value) for value in match.groups()))
        for match in CROP_PATTERN.finditer(stderr)
    )


def _representative(candidates: tuple[CropRect, ...]) -> CropRect | None:
    if not candidates:
        return None
    return Counter(candidates).most_common(1)[0][0]


def choose_crop(
    candidates: tuple[CropRect, ...],
    source_width: int,
    source_height: int,
    samples_requested: int,
) -> CropAnalysis:
    succeeded = len(candidates)
    required = min(samples_requested, max(2, math.ceil(samples_requested * 0.6)))
    if succeeded < required:
        return CropAnalysis(None, False, samples_requested, succeeded, candidates)
    best_group: list[CropRect] = []
    for candidate in candidates:
        group = [
            other
            for other in candidates
            if all(
                abs(a - b) <= 4
                for a, b in zip(
                    (candidate.width, candidate.height, candidate.x, candidate.y),
                    (other.width, other.height, other.x, other.y),
                )
            )
        ]
        if len(group) > len(best_group):
            best_group = group
    if len(best_group) < required:
        return CropAnalysis(None, False, samples_requested, succeeded, candidates)
    left = min(item.x for item in best_group)
    top = min(item.y for item in best_group)
    right = max(item.x + item.width for item in best_group)
    bottom = max(item.y + item.height for item in best_group)
    left = max(0, left - left % 2)
    top = max(0, top - top % 2)
    right = min(source_width, right + right % 2)
    bottom = min(source_height, bottom + bottom % 2)
    crop = CropRect(right - left, bottom - top, left, top)
    margins = crop.margins(source_width, source_height)
    if max(margins) < 4:
        crop = None
    return CropAnalysis(crop, True, samples_requested, succeeded, candidates)


def analyze_crop(
    input_path: str | Path,
    media: MediaInfo,
    *,
    ffmpeg: str,
    samples: int = 5,
    sample_seconds: float = 1.0,
) -> CropAnalysis:
    if (
        not media.video_streams
        or not media.video_streams[0].width
        or not media.video_streams[0].height
    ):
        raise ProbeError("cannot analyze crop without source video dimensions")
    positions = sample_positions(media.duration, samples)
    representatives: list[CropRect] = []
    for position in positions:
        command = [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-ss",
            f"{position:.3f}",
            "-i",
            str(input_path),
            "-t",
            str(sample_seconds),
            "-an",
            "-sn",
            "-vf",
            "cropdetect=limit=24:round=2:reset=0",
            "-f",
            "null",
            "-",
        ]
        proc = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if proc.returncode not in (0,):
            continue
        representative = _representative(parse_crop_candidates(proc.stderr))
        if representative:
            representatives.append(representative)
    return choose_crop(
        tuple(representatives),
        media.video_streams[0].width,
        media.video_streams[0].height,
        len(positions),
    )
