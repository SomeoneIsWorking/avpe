#!/usr/bin/env python3
"""Inspect AVP:E's live CMessage type-size database."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from avpe.control_http import request_bytes
from avpe.save_message_types import (
    MESSAGE_TYPE_DATABASE_ADDRESS,
    MESSAGE_TYPE_DATABASE_SIZE,
    parse_message_type_database,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--database-address", type=lambda value: int(value, 0),
                        default=MESSAGE_TYPE_DATABASE_ADDRESS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        inventory = parse_message_type_database(
            _read_guest_memory(args.port, args.database_address, MESSAGE_TYPE_DATABASE_SIZE)
        )
        result = {
            "schema": "avpe-message-type-database-v1",
            "database_address": args.database_address,
            "entry_count": len(inventory),
            "entries": [
                {
                    "slot": entry.slot,
                    "create_address": entry.create_address,
                    "size": entry.size,
                    "name_address": entry.name_address,
                }
                for entry in inventory
                if entry is not None
            ],
        }
        encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output is None:
            print(encoded, end="")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded)
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as error:
        print(f"FATAL message type inspection failed: {error}", file=sys.stderr)
        return 1
    return 0


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
