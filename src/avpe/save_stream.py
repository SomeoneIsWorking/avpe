"""Parse AVP:E's recursive serialized object stream after its fixed prefix."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
import struct
from typing import Any

from avpe.save_descriptor_probe import (
    EditableDescriptor,
    SerializedDescriptorBody,
    parse_serialized_descriptor_body,
)
from avpe.save_ex import (
    GDropShipSaveEx,
    GFowSaveEx,
    GObjectAISaveEx,
    GPlayerManagerSaveEx,
    GUnitSaveEx,
    parse_gdrop_ship_payload,
    parse_gfow_saver_payload,
    parse_gobject_ai_payload_from_database,
    parse_gplayer_manager_payload,
    parse_gunit_payload,
)
from avpe.save_format import (
    OBJECT_HEADER_SIZE,
    OBJECT_NESTED_OR_END_MARKER,
    OBJECT_TOP_LEVEL_OR_END_MARKER,
)
from avpe.save_message_types import MessageTypeEntry


MAX_SERIALIZED_OBJECTS = 4096
MAX_SERIALIZED_DEPTH = 64
MAX_TRAILING_PADDING_BYTES = 64

SaveExPayload = (
    GUnitSaveEx
    | GDropShipSaveEx
    | GFowSaveEx
    | GObjectAISaveEx
    | GPlayerManagerSaveEx
    | None
)


@dataclass(frozen=True)
class SaveClassMetadata:
    class_id: int
    name: str
    descriptors: tuple[EditableDescriptor, ...]
    save_ex: str


@dataclass(frozen=True)
class SerializedObject:
    index: int
    parent_index: int | None
    depth: int
    offset: int
    structure_end_offset: int
    save_ex_offset: int | None
    save_ex_end_offset: int | None
    marker: int
    class_id: int
    class_name: str
    serial: int
    state: int
    children: tuple[int, ...]
    descriptor_body: SerializedDescriptorBody
    save_ex: SaveExPayload


@dataclass(frozen=True)
class SerializedObjectStream:
    objects: tuple[SerializedObject, ...]
    top_level_objects: tuple[int, ...]
    terminator_offset: int
    trailing_padding_bytes: int


def parse_serialized_object_stream(
    data: bytes,
    class_metadata: Mapping[int, SaveClassMetadata],
    message_types: Sequence[MessageTypeEntry | None] | None = None,
) -> SerializedObjectStream:
    """Parse all objects and class-specific payloads in one bounded stream.

    The stream is depth-first for object structures: an object header is
    followed by nested objects, a nested terminator, and descriptor-defined
    fields. ``GObject::SaveAll`` writes the queued virtual ``SaveEx`` payloads
    after the complete structure of each top-level root, in object-handle
    order. The object header's state word supplies the grounded
    ``GPlayerManager`` active predicate; no payload length is guessed.
    """

    normalized_message_types = (
        None if message_types is None else tuple(message_types)
    )
    records: list[SerializedObject | None] = []
    cursor = 0
    top_level: list[int] = []
    while True:
        marker = _read_u32(data, cursor, "top-level object marker")
        if marker == OBJECT_TOP_LEVEL_OR_END_MARKER and _is_terminator(data, cursor):
            terminator_offset = cursor
            cursor += OBJECT_HEADER_SIZE
            trailing = len(data) - cursor
            if trailing > MAX_TRAILING_PADDING_BYTES or any(data[cursor:]):
                raise ValueError("object stream has nonzero or excessive trailing padding")
            return SerializedObjectStream(
                tuple(record for record in records if record is not None),
                tuple(top_level),
                terminator_offset,
                trailing,
            )
        if marker != OBJECT_TOP_LEVEL_OR_END_MARKER:
            raise ValueError("object stream is missing its top-level terminator")
        index, cursor = _parse_object(
            data,
            cursor,
            OBJECT_TOP_LEVEL_OR_END_MARKER,
            None,
            0,
            class_metadata,
            records,
        )
        for object_index in range(index, len(records)):
            record = records[object_index]
            if record is None:
                raise ValueError("object stream has an incomplete object record")
            save_ex_offset = cursor
            save_ex, consumed = _parse_save_ex(
                data[cursor:],
                class_metadata[record.class_id].save_ex,
                record.state,
                normalized_message_types,
            )
            cursor += consumed
            records[object_index] = replace(
                record,
                save_ex_offset=save_ex_offset,
                save_ex_end_offset=cursor,
                save_ex=save_ex,
            )
        top_level.append(index)


def _parse_object(
    data: bytes,
    offset: int,
    expected_marker: int,
    parent_index: int | None,
    depth: int,
    class_metadata: Mapping[int, SaveClassMetadata],
    records: list[SerializedObject | None],
) -> tuple[int, int]:
    if depth > MAX_SERIALIZED_DEPTH:
        raise ValueError("object stream nesting exceeds its bound")
    if len(records) >= MAX_SERIALIZED_OBJECTS:
        raise ValueError("object stream object count exceeds its bound")
    header = _read_header(data, offset, expected_marker)
    metadata = class_metadata.get(header[1])
    if metadata is None:
        raise ValueError(f"object stream references unknown class 0x{header[1]:08x}")

    index = len(records)
    records.append(None)
    cursor = offset + OBJECT_HEADER_SIZE
    children: list[int] = []
    while True:
        marker = _read_u32(data, cursor, "nested object marker")
        if marker != OBJECT_NESTED_OR_END_MARKER:
            raise ValueError("object stream is missing its nested terminator")
        if _is_terminator(data, cursor):
            cursor += OBJECT_HEADER_SIZE
            break
        child_index, cursor = _parse_object(
            data,
            cursor,
            OBJECT_NESTED_OR_END_MARKER,
            index,
            depth + 1,
            class_metadata,
            records,
        )
        children.append(child_index)

    descriptor_body = parse_serialized_descriptor_body(
        data[cursor:], metadata.descriptors
    )
    cursor += descriptor_body.consumed_bytes
    records[index] = SerializedObject(
        index=index,
        parent_index=parent_index,
        depth=depth,
        offset=offset,
        structure_end_offset=cursor,
        save_ex_offset=None,
        save_ex_end_offset=None,
        marker=header[0],
        class_id=header[1],
        class_name=metadata.name,
        serial=header[2],
        state=header[3],
        children=tuple(children),
        descriptor_body=descriptor_body,
        save_ex=None,
    )
    return index, cursor


def _parse_save_ex(
    data: bytes,
    implementation: str,
    state: int,
    message_types: Sequence[MessageTypeEntry | None] | None,
) -> tuple[SaveExPayload, int]:
    if implementation == "GObject":
        return None, 0
    if implementation == "GUnit":
        result = parse_gunit_payload(data)
    elif implementation == "GDropShip":
        result = parse_gdrop_ship_payload(data)
    elif implementation == "GFOWSaver":
        result = parse_gfow_saver_payload(data)
    elif implementation == "GObjectAI":
        if message_types is None:
            raise ValueError("GObjectAI SaveEx requires the message type database")
        result = parse_gobject_ai_payload_from_database(data, tuple(message_types))
    elif implementation == "GPlayerManager":
        result = parse_gplayer_manager_payload(data, (state & 0xFFFF) == 1)
    else:
        raise ValueError(f"unsupported SaveEx implementation {implementation!r}")
    return result, result.consumed_bytes


def _read_header(
    data: bytes, offset: int, expected_marker: int
) -> tuple[int, int, int, int]:
    if offset < 0 or offset + OBJECT_HEADER_SIZE > len(data):
        raise ValueError("object stream object header is truncated")
    header = struct.unpack_from("<4I", data, offset)
    if header[0] != expected_marker or _is_terminator(data, offset):
        raise ValueError("object stream contains an invalid object header")
    return header


def _read_u32(data: bytes, offset: int, label: str) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"{label} is truncated")
    return struct.unpack_from("<I", data, offset)[0]


def _is_terminator(data: bytes, offset: int) -> bool:
    return (
        offset >= 0
        and offset + OBJECT_HEADER_SIZE <= len(data)
        and data[offset + 4:offset + OBJECT_HEADER_SIZE] == b"\0" * 12
    )


def serialize_object_stream(stream: SerializedObjectStream) -> dict[str, Any]:
    """Convert a parsed stream to a JSON-safe, evidence-oriented report."""

    return {
        "object_count": len(stream.objects),
        "top_level_objects": list(stream.top_level_objects),
        "terminator_offset": stream.terminator_offset,
        "trailing_padding_bytes": stream.trailing_padding_bytes,
        "objects": [_serialize_object(record) for record in stream.objects],
    }


def _serialize_object(record: SerializedObject) -> dict[str, Any]:
    return {
        "index": record.index,
        "parent_index": record.parent_index,
        "depth": record.depth,
        "offset": record.offset,
        "structure_end_offset": record.structure_end_offset,
        "save_ex_offset": record.save_ex_offset,
        "save_ex_end_offset": record.save_ex_end_offset,
        "marker": record.marker,
        "class_id": record.class_id,
        "class_name": record.class_name,
        "serial": record.serial,
        "state": record.state,
        "children": list(record.children),
        "descriptor_fields": [
            {
                "field_id": field.field_id,
                "kind": field.kind,
                "offset": field.offset,
                "wire_size": field.wire_size,
                "raw_hex": field.raw.hex(),
                "pointer_identities": list(field.pointer_identities),
            }
            for field in record.descriptor_body.fields
        ],
        "save_ex": _serialize_value(record.save_ex),
    }


def _serialize_value(value: object) -> Any:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {
            name: _serialize_value(getattr(value, name))
            for name in value.__dataclass_fields__
        }
    return value
