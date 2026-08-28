#!/usr/bin/env python3
"""Summarize extracted AVP:E game-save record files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from avpe.save_format import parse_game_save_record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path, nargs="+", help="binary game-save records")
    parser.add_argument("--output", type=Path, help="write the summary JSON to this path")
    args = parser.parse_args()

    try:
        report = {
            "schema": "avpe-save-record-report-v1",
            "records": [
                {
                    "path": str(path),
                    "summary": parse_game_save_record(path.read_bytes()),
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


if __name__ == "__main__":
    raise SystemExit(main())
