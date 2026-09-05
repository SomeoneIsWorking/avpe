#!/usr/bin/env python3
"""Search every decoded TBF payload, reporting bounded locations and full counts."""

import argparse
import json
from pathlib import Path

from avpe.tbf_archive import Limits, search_archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--hex", action="append", default=[], help="literal bytes in hex, not a numeric word")
    parser.add_argument("--text", action="append", default=[], help="UTF-8 text bytes")
    args = parser.parse_args()
    try:
        patterns = tuple(bytes.fromhex(value) for value in args.hex) + tuple(
            value.encode("utf-8") for value in args.text)
        with args.archive.open("rb") as stream:
            data = stream.read(Limits().archive_bytes + 1)
        result = search_archive(data, patterns)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
