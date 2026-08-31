#!/usr/bin/env python3
"""Summarize extracted AVP:E game-save record files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from avpe.save_descriptor_probe import EditableDescriptor
from avpe.save_format import parse_game_save_record
from avpe.save_message_types import MESSAGE_TYPE_ENTRY_COUNT, MessageTypeEntry
from avpe.save_stream import SaveClassMetadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path, nargs="+", help="binary game-save records")
    parser.add_argument("--output", type=Path, help="write the summary JSON to this path")
    parser.add_argument(
        "--descriptor-inventory",
        type=Path,
        help="typed class descriptor inventory from inspect_save_descriptors.py",
    )
    parser.add_argument(
        "--message-types",
        type=Path,
        help="typed MessageTypeDatabase inventory for GObjectAI SaveEx",
    )
    args = parser.parse_args()

    try:
        class_metadata = (
            _load_class_metadata(args.descriptor_inventory)
            if args.descriptor_inventory is not None
            else None
        )
        message_types = (
            _load_message_types(args.message_types)
            if args.message_types is not None
            else None
        )
        report = {
            "schema": "avpe-save-record-report-v1",
            "records": [
                {
                    "path": str(path),
                    "summary": parse_game_save_record(
                        path.read_bytes(),
                        class_metadata=class_metadata,
                        message_types=message_types,
                    ),
                }
                for path in args.records
            ],
        }
    except (OSError, ValueError) as error:
        print(f"analyze-save-records: {error}", file=sys.stderr)
        return 1
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(encoded, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    return 0


def _load_class_metadata(path: Path) -> dict[int, SaveClassMetadata]:
    document = json.loads(path.read_text())
    entries = _require_list(document, "entries", "descriptor inventory")
    metadata: dict[int, SaveClassMetadata] = {}
    for value in entries:
        record = _require_object(value, "descriptor entry")
        class_id = _require_u32(record, "class_id", "descriptor entry")
        if class_id in metadata:
            raise ValueError(f"descriptor inventory repeats class 0x{class_id:08x}")
        name = record.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("descriptor entry name must be a non-empty string")
        dispatch = _require_object(record.get("save_ex"), "descriptor SaveEx")
        implementation = dispatch.get("implementation")
        if not isinstance(implementation, str) or not implementation:
            raise ValueError("descriptor SaveEx implementation must be a non-empty string")
        descriptors = []
        for item in _require_list(record, "descriptors", "descriptor entry"):
            descriptor = _require_object(item, "editable descriptor")
            descriptors.append(
                EditableDescriptor(
                    field_id=_require_u32(descriptor, "field_id", "editable descriptor"),
                    size=_require_u16(descriptor, "size", "editable descriptor"),
                    kind=_require_u8(descriptor, "kind", "editable descriptor"),
                    flags=_require_u8(descriptor, "flags", "editable descriptor"),
                    object_offset=_require_u32(
                        descriptor, "object_offset", "editable descriptor"
                    ),
                )
            )
        metadata[class_id] = SaveClassMetadata(
            class_id, name, tuple(descriptors), implementation
        )
    if not metadata:
        raise ValueError("descriptor inventory contains no entries")
    return metadata


def _load_message_types(path: Path) -> tuple[MessageTypeEntry | None, ...]:
    document = json.loads(path.read_text())
    values = _require_list(document, "entries", "message type inventory")
    entries: list[MessageTypeEntry | None] = [None] * MESSAGE_TYPE_ENTRY_COUNT
    for value in values:
        record = _require_object(value, "message type entry")
        slot = _require_u8(record, "slot", "message type entry")
        if entries[slot] is not None:
            raise ValueError(f"message type inventory repeats slot 0x{slot:02x}")
        entries[slot] = MessageTypeEntry(
            slot,
            _require_u32(record, "create_address", "message type entry"),
            _require_u32(record, "size", "message type entry"),
            _require_u32(record, "name_address", "message type entry"),
        )
    return tuple(entries)


def _require_object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _require_list(value: object, key: str, label: str) -> list[object]:
    record = _require_object(value, label)
    items = record.get(key)
    if not isinstance(items, list):
        raise ValueError(f"{label}.{key} must be a list")
    return items


def _require_integer(record: dict[str, object], key: str, label: str, maximum: int) -> int:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValueError(f"{label}.{key} must be an integer in [0, {maximum}]")
    return value


def _require_u8(record: dict[str, object], key: str, label: str) -> int:
    return _require_integer(record, key, label, 0xFF)


def _require_u16(record: dict[str, object], key: str, label: str) -> int:
    return _require_integer(record, key, label, 0xFFFF)


def _require_u32(record: dict[str, object], key: str, label: str) -> int:
    return _require_integer(record, key, label, 0xFFFFFFFF)


if __name__ == "__main__":
    raise SystemExit(main())
