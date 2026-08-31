"""Grounded parser for AVP:E's BWJ-compressed game-save records."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
import struct
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from avpe.save_message_types import MessageTypeEntry
    from avpe.save_stream import SaveClassMetadata


OUTER_RECORD_SIZE = 0x118
OUTER_FIELDS_OFFSET = 0x100
GAME_SAVE_SLOT_SIZE = 0x7E400
BWJ_MODE_OFFSET = 0
GAME_LEVEL_OFFSET = 0
GAME_LEVEL_SIZE = 0x20
GAME_TIME_OFFSET = GAME_LEVEL_OFFSET + GAME_LEVEL_SIZE
HANDLE_BITMAP_OFFSET = GAME_TIME_OFFSET + 4
HANDLE_BITMAP_SIZE = 0x2000
REPEATED_GAME_TIME_OFFSET = HANDLE_BITMAP_OFFSET + HANDLE_BITMAP_SIZE
OBJECT_STREAM_OFFSET = REPEATED_GAME_TIME_OFFSET + 4
OBJECT_TOP_LEVEL_OR_END_MARKER = 0x7FEA419D
OBJECT_NESTED_OR_END_MARKER = 0xBADF00DE
OBJECT_HEADER_SIZE = 0x10
DEFAULT_MAX_DECOMPRESSED_BYTES = GAME_SAVE_SLOT_SIZE * 64


@dataclass(frozen=True)
class BwjDecoded:
    """Decoded words and the compressed prefix consumed through the terminator."""

    data: bytes
    mode: int
    shift: int
    length_mask: int
    consumed_bytes: int


def decode_bwj(stream: bytes, max_output_bytes: int) -> BwjDecoded:
    """Decode one title BWJ stream, stopping at its explicit zero token.

    BWJ stores little-endian 16-bit words. Each control word describes sixteen
    literal or back-reference words; a back-reference token uses the high bits
    for a word distance and the low bits for a word length. The caller supplies
    the output bound because compressed save data is user-controlled.
    """

    if max_output_bytes <= 0 or max_output_bytes % 2 != 0:
        raise ValueError("BWJ output bound must be a positive even number")
    if len(stream) < 4:
        raise ValueError("BWJ stream is truncated before its mode and control word")

    mode = _read_word(stream, BWJ_MODE_OFFSET)
    if mode == 0 or mode & 0x8000:
        raise ValueError(f"unsupported BWJ mode 0x{mode:04x}")
    shift = 0
    normalized_mode = mode
    while not normalized_mode & 0x8000:
        normalized_mode <<= 1
        shift += 1
    length_mask = (1 << shift) - 1

    output = bytearray()
    position = 2
    while True:
        control = _read_word(stream, position)
        position += 2
        for bit in range(16):
            if control & (0x8000 >> bit):
                token = _read_word(stream, position)
                position += 2
                if token == 0:
                    return BwjDecoded(
                        bytes(output), mode, shift, length_mask, position
                    )
                distance_words = token >> shift
                length_words = token & length_mask
                if distance_words == 0 or length_words < 2:
                    raise ValueError(
                        f"invalid BWJ back-reference 0x{token:04x}"
                    )
                if distance_words > len(output) // 2:
                    raise ValueError(
                        f"BWJ back-reference distance exceeds output: {distance_words}"
                    )
                _ensure_output_capacity(
                    len(output), length_words * 2, max_output_bytes
                )
                for _ in range(length_words):
                    source = len(output) - distance_words * 2
                    output.extend(output[source:source + 2])
            else:
                literal = _read_word(stream, position)
                position += 2
                _ensure_output_capacity(len(output), 2, max_output_bytes)
                output.extend(struct.pack("<H", literal))


def parse_game_save_record(
    record: bytes,
    max_decompressed_bytes: int = DEFAULT_MAX_DECOMPRESSED_BYTES,
    class_metadata: Mapping[int, "SaveClassMetadata"] | None = None,
    message_types: Sequence["MessageTypeEntry | None"] | None = None,
) -> dict[str, Any]:
    """Parse the outer record, prefix, and optionally its typed object stream."""

    if len(record) < OUTER_RECORD_SIZE + 4:
        raise ValueError("game-save record is shorter than its outer record")
    outer_values = struct.unpack_from("<6I", record, OUTER_FIELDS_OFFSET)
    decoded = decode_bwj(record[OUTER_RECORD_SIZE:], max_decompressed_bytes)
    stream = _parse_game_save_stream(decoded.data, class_metadata, message_types)
    return {
        "record_size": len(record),
        "outer": {
            "profile_crc32": outer_values[0],
            "unknown_104": outer_values[1],
            "game_data_revision": outer_values[2],
            "field_10c": outer_values[3],
            "payload_size": outer_values[4],
            "field_114": outer_values[5],
        },
        "bwj": {
            "mode": decoded.mode,
            "shift": decoded.shift,
            "length_mask": decoded.length_mask,
            "compressed_bytes_consumed": decoded.consumed_bytes,
            "decompressed_bytes": len(decoded.data),
        },
        "stream": stream,
    }


def _parse_game_save_stream(
    data: bytes,
    class_metadata: Mapping[int, "SaveClassMetadata"] | None,
    message_types: Sequence["MessageTypeEntry | None"] | None,
) -> dict[str, Any]:
    if len(data) < OBJECT_STREAM_OFFSET:
        raise ValueError("decoded game-save stream is missing its fixed prefix")
    level_bytes = data[GAME_LEVEL_OFFSET:GAME_LEVEL_OFFSET + GAME_LEVEL_SIZE]
    try:
        terminator = level_bytes.index(0)
    except ValueError as error:
        raise ValueError("game-save level identifier is not NUL-terminated") from error
    try:
        level = level_bytes[:terminator].decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("game-save level identifier is not ASCII") from error

    game_time_bytes = data[GAME_TIME_OFFSET:GAME_TIME_OFFSET + 4]
    repeated_time_bytes = data[REPEATED_GAME_TIME_OFFSET:REPEATED_GAME_TIME_OFFSET + 4]
    game_time = struct.unpack("<f", game_time_bytes)[0]
    repeated_game_time = struct.unpack("<f", repeated_time_bytes)[0]
    if not math.isfinite(game_time) or not math.isfinite(repeated_game_time):
        raise ValueError("game-save time prefix is not finite")

    object_words = memoryview(data)[OBJECT_STREAM_OFFSET:]
    marker_counts = {
        "top_level_or_end": 0,
        "nested_or_end": 0,
    }
    class_id_counts: dict[int, int] = {}
    object_summary = {
        "header_size": OBJECT_HEADER_SIZE,
        "top_level_starts": 0,
        "top_level_terminators": 0,
        "nested_starts": 0,
        "nested_terminators": 0,
        "class_id_counts": class_id_counts,
        "max_depth": 0,
        "active_objects": 0,
        "structure_balanced": False,
    }
    for offset in range(0, len(object_words) - 3, 4):
        marker = struct.unpack_from("<I", object_words, offset)[0]
        if marker == OBJECT_TOP_LEVEL_OR_END_MARKER:
            marker_counts["top_level_or_end"] += 1
            _observe_object_marker(object_words, offset, marker, object_summary)
        elif marker == OBJECT_NESTED_OR_END_MARKER:
            marker_counts["nested_or_end"] += 1
            _observe_object_marker(object_words, offset, marker, object_summary)

    object_summary["structure_balanced"] = (
        object_summary["active_objects"] == 0
        and object_summary["top_level_terminators"] == 1
        and object_summary["nested_terminators"]
        == object_summary["top_level_starts"] + object_summary["nested_starts"]
    )
    if not object_summary["structure_balanced"]:
        raise ValueError("game-save object stream is unbalanced")

    result = {
        "level": level,
        "level_suffix_hex": level_bytes[terminator + 1:].hex(),
        "game_time": game_time,
        "repeated_game_time": repeated_game_time,
        "game_time_bytes_match": game_time_bytes == repeated_time_bytes,
        "handle_bitmap_bytes": HANDLE_BITMAP_SIZE,
        "handle_bitmap_nonzero_words": sum(
            1
            for offset in range(0, HANDLE_BITMAP_SIZE, 4)
            if data[HANDLE_BITMAP_OFFSET + offset:HANDLE_BITMAP_OFFSET + offset + 4]
            != b"\0\0\0\0"
        ),
        "object_stream_offset": OBJECT_STREAM_OFFSET,
        "object_marker_counts": marker_counts,
        "object_stream_summary": object_summary,
    }
    if class_metadata is not None:
        from avpe.save_stream import (
            parse_serialized_object_stream,
            serialize_object_stream,
        )

        parsed_objects = parse_serialized_object_stream(
            bytes(object_words), class_metadata, message_types
        )
        result["serialized_objects"] = serialize_object_stream(parsed_objects)
    return result


def _observe_object_marker(
    data: memoryview,
    offset: int,
    marker: int,
    summary: dict[str, Any],
) -> None:
    if offset + OBJECT_HEADER_SIZE > len(data):
        raise ValueError("game-save object header is truncated")
    words = struct.unpack_from("<4I", data, offset)
    if words[1:] == (0, 0, 0):
        if marker == OBJECT_TOP_LEVEL_OR_END_MARKER:
            summary["top_level_terminators"] += 1
            if summary["active_objects"] != 0:
                raise ValueError("game-save object stream terminates inside an object")
        else:
            summary["nested_terminators"] += 1
            if summary["active_objects"] == 0:
                raise ValueError("game-save object stream closes an empty object stack")
            summary["active_objects"] -= 1
        return

    if marker == OBJECT_TOP_LEVEL_OR_END_MARKER:
        summary["top_level_starts"] += 1
    else:
        summary["nested_starts"] += 1
    class_id = words[1]
    class_id_counts = summary["class_id_counts"]
    class_id_counts[class_id] = class_id_counts.get(class_id, 0) + 1
    summary["active_objects"] += 1
    summary["max_depth"] = max(summary["max_depth"], summary["active_objects"])


def _read_word(data: bytes, offset: int) -> int:
    if offset + 2 > len(data):
        raise ValueError("BWJ stream ended before a complete word")
    return struct.unpack_from("<H", data, offset)[0]


def _ensure_output_capacity(current_size: int, addition: int, maximum: int) -> None:
    if current_size + addition > maximum:
        raise ValueError("BWJ output exceeds the configured bound")
