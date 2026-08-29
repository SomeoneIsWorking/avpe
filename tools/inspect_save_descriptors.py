#!/usr/bin/env python3
"""Inspect live AVP:E save class descriptors through the control channel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from avpe.control_http import request_bytes
from avpe.save_descriptor_probe import (
    CLASS_TYPE_DATABASE_ADDRESS,
    inspect_class_type_database,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--save-report", type=Path, required=True,
                        help="analyze_save_records.py JSON report supplying class IDs")
    parser.add_argument("--database-address", type=lambda value: int(value, 0),
                        default=CLASS_TYPE_DATABASE_ADDRESS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        report = json.loads(args.save_report.read_text())
        class_ids = _class_ids_from_report(report)
        inventory = inspect_class_type_database(
            lambda address, length: _read_guest_memory(args.port, address, length),
            class_ids,
            args.database_address,
        )
        encoded = json.dumps(inventory, indent=2, sort_keys=True) + "\n"
        if args.output is None:
            print(encoded, end="")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded)
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as error:
        print(f"FATAL save descriptor inspection failed: {error}", file=sys.stderr)
        return 1
    return 0


def _class_ids_from_report(report: object) -> set[int]:
    if not isinstance(report, dict) or not isinstance(report.get("records"), list):
        raise ValueError("save report must contain a records list")
    class_ids: set[int] = set()
    for record in report["records"]:
        try:
            counts = record["summary"]["stream"]["object_stream_summary"]["class_id_counts"]
        except (KeyError, TypeError) as error:
            raise ValueError("save report record is missing class ID counts") from error
        if not isinstance(counts, dict):
            raise ValueError("save report class ID counts must be an object")
        for value in counts:
            class_id = int(value)
            if class_id < 0 or class_id > 0xFFFFFFFF:
                raise ValueError("save report class ID is outside u32")
            class_ids.add(class_id)
    if not class_ids:
        raise ValueError("save report contains no class IDs")
    return class_ids


def _read_guest_memory(port: int, address: int, length: int) -> bytes:
    status, body = request_bytes(
        port, "GET", f"/mem/read?addr=0x{address:08x}&len={length:x}"
    )
    if status != 200:
        raise RuntimeError(f"guest memory read returned HTTP {status}")
    response = json.loads(body)
    if not isinstance(response, dict) or response.get("len") != length:
        raise ValueError("guest memory read returned malformed length")
    value = response.get("hex")
    if not isinstance(value, str):
        raise ValueError("guest memory read returned malformed hex")
    try:
        raw = bytes.fromhex(value)
    except ValueError as error:
        raise ValueError("guest memory read returned invalid hex") from error
    if len(raw) != length:
        raise ValueError("guest memory read returned the wrong byte count")
    return raw


if __name__ == "__main__":
    raise SystemExit(main())
