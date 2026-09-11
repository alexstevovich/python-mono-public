from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from comfyui_metadata.container import (
    ImageFormat,
    build_exif,
    exif_fields,
    image_format,
    png_text_fields,
    replace_png_text,
    replace_webp_exif,
    webp_exif,
)

from .errors import MetadataVerificationError


@dataclass(frozen=True)
class Metadata:
    parameters: str


class Outcome(Enum):
    COPIED = "copied"
    NO_METADATA = "no_metadata"


def _decode_webp_comment(value: bytes | None) -> str | None:
    if value is None or not value.startswith(b"UNICODE\0"):
        return None
    body = value.removeprefix(b"UNICODE\0")
    if len(body) % 2:
        return None
    try:
        return body.decode("utf-16-be")
    except UnicodeDecodeError:
        return None


def extract_metadata(data: bytes) -> Metadata | None:
    if image_format(data) is ImageFormat.PNG:
        parameters = png_text_fields(data).get("parameters")
    else:
        exif = webp_exif(data)
        fields = exif_fields(exif) if exif is not None else None
        parameters = _decode_webp_comment(fields[1]) if fields is not None else None
    return Metadata(parameters) if parameters is not None else None


def _updated_destination(data: bytes, metadata: Metadata) -> bytes:
    if image_format(data) is ImageFormat.PNG:
        return replace_png_text(data, {"parameters": metadata.parameters})
    comment = b"UNICODE\0" + metadata.parameters.encode("utf-16-be")
    return replace_webp_exif(data, build_exif(None, comment))


def _write_atomic(path: Path, data: bytes) -> None:
    parent = path.parent if path.parent != Path("") else Path(".")
    descriptor, name = tempfile.mkstemp(
        prefix=".a1111-meta-", suffix=".tmp", dir=parent
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def copy_metadata(
    source: str | os.PathLike[str], destination: str | os.PathLike[str]
) -> Outcome:
    metadata = read_metadata(source)
    if metadata is None:
        return Outcome.NO_METADATA
    destination_path = Path(destination)
    updated = _updated_destination(destination_path.read_bytes(), metadata)
    if extract_metadata(updated) != metadata:
        raise MetadataVerificationError("written A1111 metadata could not be verified")
    _write_atomic(destination_path, updated)
    return Outcome.COPIED


def read_metadata(path: str | os.PathLike[str]) -> Metadata | None:
    return extract_metadata(Path(path).read_bytes())
