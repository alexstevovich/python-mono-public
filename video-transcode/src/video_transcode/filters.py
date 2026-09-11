from __future__ import annotations


def deinterlace_filter(policy: str) -> tuple[str | None, str]:
    """Return a conservative, single-rate FFmpeg deinterlace filter."""
    if policy == "off":
        return None, "off"
    if policy == "on":
        return "bwdif=mode=send_frame:parity=auto:deint=all", "on (bwdif, single-rate)"
    if policy == "auto":
        return (
            "bwdif=mode=send_frame:parity=auto:deint=interlaced",
            "auto (flagged frames only)",
        )
    raise ValueError("deinterlace policy must be auto, off, or on")
