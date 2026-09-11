from __future__ import annotations

import subprocess
import threading
import time
from collections.abc import Callable
from datetime import datetime

from .errors import TranscodeExecutionError
from .models import ProgressEvent, TranscodeJob, TranscodeResult

ProgressCallback = Callable[[ProgressEvent], None]


def _number(value: str | None) -> float | None:
    if not value or value in {"N/A", "nan"}:
        return None
    try:
        return float(value.rstrip("x"))
    except ValueError:
        return None


def _encoded_seconds(values: dict[str, str]) -> float:
    microseconds = _number(values.get("out_time_us"))
    if microseconds is not None:
        return max(0.0, microseconds / 1_000_000)
    timestamp = values.get("out_time", "")
    try:
        hours, minutes, seconds = timestamp.split(":")
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except (ValueError, AttributeError):
        return 0.0


def parse_progress(
    values: dict[str, str], duration: float | None, elapsed: float
) -> ProgressEvent:
    encoded = _encoded_seconds(values)
    percent = (
        min(100.0, encoded / duration * 100) if duration and duration > 0 else None
    )
    finished = values.get("progress") == "end"
    if finished and percent is not None:
        percent = 100.0
    speed = _number(values.get("speed"))
    eta = (
        max(0.0, duration - encoded) / speed
        if duration and speed and speed > 0
        else None
    )
    size = _number(values.get("total_size"))
    return ProgressEvent(
        percent=percent,
        encoded_seconds=encoded,
        duration_seconds=duration,
        fps=_number(values.get("fps")),
        speed=speed,
        output_size=int(size) if size is not None else None,
        elapsed_seconds=elapsed,
        finished=finished,
        estimated_remaining_seconds=0.0 if finished and duration else eta,
    )


def execute_job(
    job: TranscodeJob,
    *,
    duration: float | None = None,
    progress_callback: ProgressCallback | None = None,
    started_at: datetime | None = None,
) -> TranscodeResult:
    started_at = started_at or datetime.now().astimezone()
    started = time.monotonic()
    try:
        source_size = job.input_path.stat().st_size
    except OSError:
        source_size = None
    if progress_callback is None:
        proc = subprocess.run(
            job.command, text=True, stderr=subprocess.PIPE, check=False
        )
        stderr = proc.stderr
        returncode = proc.returncode
    else:
        proc = subprocess.Popen(
            job.command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
        )
        stderr_parts: list[str] = []

        def drain_stderr() -> None:
            assert proc.stderr is not None
            stderr_parts.extend(proc.stderr)

        reader = threading.Thread(target=drain_stderr, daemon=True)
        reader.start()
        values: dict[str, str] = {}
        assert proc.stdout is not None
        try:
            for raw_line in proc.stdout:
                key, separator, value = raw_line.strip().partition("=")
                if not separator:
                    continue
                values[key] = value
                if key == "progress":
                    progress_callback(
                        parse_progress(values, duration, time.monotonic() - started)
                    )
                    values = {}
            returncode = proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            proc.wait()
            raise
        finally:
            reader.join()
            proc.stdout.close()
            assert proc.stderr is not None
            proc.stderr.close()
        stderr = "".join(stderr_parts)
    elapsed = time.monotonic() - started
    if returncode:
        raise TranscodeExecutionError(
            f"ffmpeg exited with status {returncode}: {stderr[-4000:]}",
            job.command,
            returncode,
        )
    try:
        output_size = job.output_path.stat().st_size
    except OSError:
        output_size = None
    return TranscodeResult(
        job,
        returncode,
        stderr,
        elapsed,
        output_size,
        source_size,
        started_at,
        datetime.now().astimezone(),
    )
