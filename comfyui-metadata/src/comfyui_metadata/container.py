from __future__ import annotations

import binascii
import struct
import zlib
from collections.abc import Iterator, Sequence
from enum import Enum

from .errors import InvalidImageContainerError, UnsupportedImageContainerError

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class ImageFormat(Enum):
    PNG = "png"
    WEBP = "webp"


def image_format(data: bytes) -> ImageFormat:
    if data.startswith(PNG_SIGNATURE):
        return ImageFormat.PNG
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ImageFormat.WEBP
    raise UnsupportedImageContainerError()


def _png_chunks(data: bytes) -> Iterator[tuple[bytes, bytes, bytes]]:
    if image_format(data) is not ImageFormat.PNG:
        raise UnsupportedImageContainerError()
    position = len(PNG_SIGNATURE)
    found_end = False
    while position + 12 <= len(data):
        size = struct.unpack_from(">I", data, position)[0]
        end = position + 12 + size
        if end > len(data):
            raise InvalidImageContainerError("PNG")
        kind = data[position + 4 : position + 8]
        payload = data[position + 8 : position + 8 + size]
        expected_crc = struct.unpack_from(">I", data, position + 8 + size)[0]
        actual_crc = binascii.crc32(kind + payload) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            raise InvalidImageContainerError("PNG")
        yield kind, payload, data[position:end]
        position = end
        if kind == b"IEND":
            found_end = True
            break
    if not found_end or position != len(data):
        raise InvalidImageContainerError("PNG")


def _png_text(payload: bytes, kind: bytes) -> tuple[str, str] | None:
    try:
        keyword, remainder = payload.split(b"\0", 1)
        key = keyword.decode("latin-1")
        if kind == b"tEXt":
            return key, remainder.decode("latin-1")
        if kind == b"zTXt":
            method, compressed = remainder[0], remainder[1:]
            if method != 0:
                return None
            return key, zlib.decompress(compressed).decode("latin-1")
        if kind == b"iTXt":
            if len(remainder) < 2:
                return None
            compressed, method = remainder[0], remainder[1]
            language_end = remainder.find(b"\0", 2)
            if language_end < 0:
                return None
            translated_end = remainder.find(b"\0", language_end + 1)
            if translated_end < 0:
                return None
            text = remainder[translated_end + 1 :]
            if compressed:
                if method != 0:
                    return None
                text = zlib.decompress(text)
            return key, text.decode("utf-8")
    except (IndexError, UnicodeDecodeError, ValueError, zlib.error):
        return None
    return None


def png_text_fields(data: bytes) -> dict[str, str]:
    fields: dict[str, str] = {}
    for kind, payload, _ in _png_chunks(data):
        if kind in (b"tEXt", b"zTXt", b"iTXt"):
            decoded = _png_text(payload, kind)
            if decoded is not None:
                fields[decoded[0]] = decoded[1]
    return fields


def _make_png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = binascii.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def replace_png_text(data: bytes, replacements: dict[str, str]) -> bytes:
    output = bytearray(PNG_SIGNATURE)
    for kind, payload, raw in _png_chunks(data):
        decoded = (
            _png_text(payload, kind) if kind in (b"tEXt", b"zTXt", b"iTXt") else None
        )
        if kind == b"IEND":
            for key, value in replacements.items():
                text = key.encode("latin-1") + b"\0\0\0\0\0" + value.encode("utf-8")
                output.extend(_make_png_chunk(b"iTXt", text))
        if decoded is None or decoded[0] not in replacements:
            output.extend(raw)
    return bytes(output)


def _webp_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    if image_format(data) is not ImageFormat.WEBP:
        raise UnsupportedImageContainerError()
    if len(data) < 12 or struct.unpack_from("<I", data, 4)[0] != len(data) - 8:
        raise InvalidImageContainerError("WebP")
    chunks: list[tuple[bytes, bytes]] = []
    position = 12
    while position + 8 <= len(data):
        kind = data[position : position + 4]
        size = struct.unpack_from("<I", data, position + 4)[0]
        end = position + 8 + size
        if end > len(data):
            raise InvalidImageContainerError("WebP")
        chunks.append((kind, data[position + 8 : end]))
        position = end + (size & 1)
    if position != len(data):
        raise InvalidImageContainerError("WebP")
    return chunks


def webp_exif(data: bytes) -> bytes | None:
    return next(
        (payload for kind, payload in _webp_chunks(data) if kind == b"EXIF"), None
    )


def _webp_dimensions(chunks: Sequence[tuple[bytes, bytes]]) -> tuple[int, int] | None:
    for kind, payload in chunks:
        if kind == b"VP8 " and len(payload) >= 10 and payload[3:6] == b"\x9d\x01\x2a":
            width = struct.unpack_from("<H", payload, 6)[0] & 0x3FFF
            height = struct.unpack_from("<H", payload, 8)[0] & 0x3FFF
            return width, height
        if kind == b"VP8L" and len(payload) >= 5 and payload[0] == 0x2F:
            packed = struct.unpack_from("<I", payload, 1)[0]
            return (packed & 0x3FFF) + 1, ((packed >> 14) & 0x3FFF) + 1
    return None


def replace_webp_exif(data: bytes, exif: bytes) -> bytes:
    chunks = [
        (kind, payload) for kind, payload in _webp_chunks(data) if kind != b"EXIF"
    ]
    for index, (kind, payload) in enumerate(chunks):
        if kind == b"VP8X":
            if len(payload) < 10:
                raise InvalidImageContainerError("WebP")
            updated = bytes([payload[0] | 0x08]) + payload[1:]
            chunks[index] = (kind, updated)
            break
    else:
        dimensions = _webp_dimensions(chunks)
        if dimensions is None:
            raise InvalidImageContainerError("WebP")
        width, height = dimensions
        if width < 1 or height < 1 or width > 0x1000000 or height > 0x1000000:
            raise InvalidImageContainerError("WebP")
        vp8x = (
            b"\x08\0\0\0"
            + (width - 1).to_bytes(3, "little")
            + (height - 1).to_bytes(3, "little")
        )
        chunks.insert(0, (b"VP8X", vp8x))
    chunks.append((b"EXIF", exif))

    body = bytearray(b"WEBP")
    for kind, payload in chunks:
        body.extend(kind)
        body.extend(struct.pack("<I", len(payload)))
        body.extend(payload)
        if len(payload) & 1:
            body.append(0)
    return b"RIFF" + struct.pack("<I", len(body)) + bytes(body)


def exif_fields(exif: bytes) -> tuple[bytes | None, bytes | None] | None:
    tiff = exif[6:] if exif.startswith(b"Exif\0\0") else exif
    if len(tiff) < 8 or tiff[:2] not in (b"II", b"MM"):
        return None
    byte_order = "little" if tiff[:2] == b"II" else "big"

    def u16(position: int) -> int | None:
        part = tiff[position : position + 2]
        return int.from_bytes(part, byte_order) if len(part) == 2 else None

    def u32(position: int) -> int | None:
        part = tiff[position : position + 4]
        return int.from_bytes(part, byte_order) if len(part) == 4 else None

    if u16(2) != 42:
        return None
    ifd = u32(4)
    if ifd is None:
        return None
    count = u16(ifd)
    if count is None:
        return None
    description: bytes | None = None
    exif_ifd: int | None = None
    for index in range(count):
        position = ifd + 2 + index * 12
        tag, size, offset = u16(position), u32(position + 4), u32(position + 8)
        if tag is None or size is None or offset is None:
            return None
        if tag == 0x010E:
            description = (
                tiff[offset : offset + size] if offset + size <= len(tiff) else None
            )
        elif tag == 0x8769:
            exif_ifd = offset

    comment: bytes | None = None
    if exif_ifd is not None:
        count = u16(exif_ifd)
        if count is None:
            return None
        for index in range(count):
            position = exif_ifd + 2 + index * 12
            tag, size, offset = u16(position), u32(position + 4), u32(position + 8)
            if tag is None or size is None or offset is None:
                return None
            if tag == 0x9286:
                comment = (
                    tiff[offset : offset + size] if offset + size <= len(tiff) else None
                )
    return description, comment


def build_exif(description: bytes | None, comment: bytes | None) -> bytes:
    entry_count = 2 if description is not None else 1
    root_ifd = 8
    exif_ifd = root_ifd + 2 + entry_count * 12 + 4
    data_start = exif_ifd + 2 + (12 if comment is not None else 0) + 4
    tiff = bytearray(data_start)
    tiff[:2] = b"MM"
    struct.pack_into(">H", tiff, 2, 42)
    struct.pack_into(">I", tiff, 4, root_ifd)
    struct.pack_into(">H", tiff, root_ifd, entry_count)
    position = root_ifd + 2
    extra = bytearray()

    def entry(at: int, tag: int, kind: int, count: int, value: int) -> None:
        struct.pack_into(">HHII", tiff, at, tag, kind, count, value)

    if description is not None:
        value = description + b"\0"
        entry(position, 0x010E, 2, len(value), data_start + len(extra))
        extra.extend(value)
        if len(extra) & 1:
            extra.append(0)
        position += 12
    entry(position, 0x8769, 4, 1, exif_ifd)
    struct.pack_into(">H", tiff, exif_ifd, int(comment is not None))
    if comment is not None:
        entry(exif_ifd + 2, 0x9286, 7, len(comment), data_start + len(extra))
        extra.extend(comment)
    tiff.extend(extra)
    return bytes(tiff)
