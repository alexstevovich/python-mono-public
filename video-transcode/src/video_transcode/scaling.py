from __future__ import annotations

import math

from .models import ResolutionLimit

LIMITS = {
    ResolutionLimit.SD_480: (854, 480),
    ResolutionLimit.HD_720: (1280, 720),
    ResolutionLimit.HD_1080: (1920, 1080),
    ResolutionLimit.QHD_1440: (2560, 1440),
    ResolutionLimit.UHD_2160: (3840, 2160),
}


def _even(value: float) -> int:
    return max(2, int(math.floor(value / 2) * 2))


def fit_dimensions(
    width: int, height: int, limit: ResolutionLimit, allow_upscale: bool = False
) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        raise ValueError("dimensions must be positive")
    if limit == ResolutionLimit.NONE:
        return width, height
    landscape_max = LIMITS[limit]
    max_width, max_height = landscape_max if width >= height else landscape_max[::-1]
    scale = min(max_width / width, max_height / height)
    if not allow_upscale:
        scale = min(scale, 1.0)
    if scale == 1.0:
        return width, height
    return _even(width * scale), _even(height * scale)


def explicit_dimensions(
    width: int,
    height: int,
    target_width: int | None,
    target_height: int | None,
    allow_upscale: bool,
) -> tuple[int, int]:
    if target_width is None and target_height is None:
        return width, height
    scale = min(
        target_width / width if target_width else float("inf"),
        target_height / height if target_height else float("inf"),
    )
    if not allow_upscale:
        scale = min(scale, 1.0)
    return _even(width * scale), _even(height * scale)
