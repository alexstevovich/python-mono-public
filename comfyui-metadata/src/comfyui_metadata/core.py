from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .container import (
    ImageFormat,
    build_exif,
    exif_fields,
    image_format,
    png_text_fields,
    replace_png_text,
    replace_webp_exif,
    webp_exif,
)
from .errors import InvalidComfyUIJsonError, MissingWorkflowError


@dataclass(frozen=True)
class Metadata:
    workflow: Any
    prompt: Any | None = None


class Outcome(Enum):
    COPIED = "copied"
    NO_METADATA = "no_metadata"


def _load_json(key: str, value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        raise InvalidComfyUIJsonError(key, str(error)) from error


def _extract_png(data: bytes) -> Metadata | None:
    fields = png_text_fields(data)
    prompt = _load_json("prompt", fields["prompt"]) if "prompt" in fields else None
    workflow = (
        _load_json("workflow", fields["workflow"]) if "workflow" in fields else None
    )
    if workflow is not None:
        return Metadata(workflow=workflow, prompt=prompt)
    if prompt is not None:
        raise MissingWorkflowError()
    return None


def _decode_utf8(value: bytes | None) -> str | None:
    if value is None:
        return None
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _extract_webp(data: bytes) -> Metadata | None:
    exif = webp_exif(data)
    if exif is None:
        return None
    fields = exif_fields(exif)
    if fields is None:
        return None
    description, comment = fields
    if description is not None and description.endswith(b"\0"):
        description = description[:-1]
    workflow_text = _decode_utf8(description)
    prompt_text = _decode_utf8(comment)
    if workflow_text is None or not workflow_text.startswith("Workflow:"):
        return None
    workflow = _load_json("workflow", workflow_text.removeprefix("Workflow:"))
    prompt = None
    prefix = "ASCII\0\0\0Prompt:"
    if prompt_text is not None and prompt_text.startswith(prefix):
        prompt = _load_json("prompt", prompt_text.removeprefix(prefix))
    return Metadata(workflow=workflow, prompt=prompt)


def extract_metadata(data: bytes) -> Metadata | None:
    format_ = image_format(data)
    return _extract_png(data) if format_ is ImageFormat.PNG else _extract_webp(data)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _updated_destination(data: bytes, metadata: Metadata) -> bytes:
    if image_format(data) is ImageFormat.PNG:
        fields = {"workflow": _json(metadata.workflow)}
        if metadata.prompt is not None:
            fields["prompt"] = _json(metadata.prompt)
        return replace_png_text(data, fields)
    description = f"Workflow:{_json(metadata.workflow)}".encode()
    comment = (
        b"ASCII\0\0\0Prompt:" + _json(metadata.prompt).encode()
        if metadata.prompt is not None
        else None
    )
    return replace_webp_exif(data, build_exif(description, comment))


def _write_atomic(path: Path, data: bytes) -> None:
    parent = path.parent if path.parent != Path("") else Path(".")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".image-meta-", suffix=".tmp", dir=parent
    )
    temporary = Path(temporary_name)
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
    source_path = Path(source)
    destination_path = Path(destination)
    metadata = extract_metadata(source_path.read_bytes())
    if metadata is None:
        return Outcome.NO_METADATA
    updated = _updated_destination(destination_path.read_bytes(), metadata)
    if extract_metadata(updated) != metadata:
        raise MissingWorkflowError()
    _write_atomic(destination_path, updated)
    return Outcome.COPIED


def read_metadata(path: str | os.PathLike[str]) -> Metadata | None:
    return extract_metadata(Path(path).read_bytes())


def metadata_for_webp(metadata: Metadata | None) -> bytes | None:
    if metadata is None:
        return None
    description = f"Workflow:{_json(metadata.workflow)}".encode()
    comment = (
        b"ASCII\0\0\0Prompt:" + _json(metadata.prompt).encode()
        if metadata.prompt is not None
        else None
    )
    return build_exif(description, comment)
