#!/usr/bin/env python3
"""Summarize captured AVP:E BIOS/IOP trace artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from avpe.bios_inventory import combine_bios_inventories, summarize_bios_artifact


REPORT_SCHEMA = "avpe-bios-inventory-report-v2"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "artifacts", type=Path, nargs="+", help="captured BIOS trace JSON files"
    )
    parser.add_argument(
        "--output", type=Path, help="write the inventory JSON to this path"
    )
    args = parser.parse_args()

    try:
        inventories = [
            summarize_bios_artifact(_load_json(path)) for path in args.artifacts
        ]
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))
    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "aggregate": combine_bios_inventories(inventories),
        "captures": inventories,
    }
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(encoded, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    return 0


def _load_json(path: Path) -> object:
    return json.loads(path.read_text())


if __name__ == "__main__":
    raise SystemExit(main())
