#!/usr/bin/env python3
"""CLI for the canonical streaming raw-sector converter."""

import argparse
import sys
from pathlib import Path

from avpe.raw_sector import RawSectorError, strip_image


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("raw_bin", type=Path)
    ap.add_argument("out_iso", type=Path)
    args = ap.parse_args()
    try:
        report = strip_image(args.raw_bin, args.out_iso)
    except (OSError, RawSectorError) as error:
        print(f"FATAL {error}", file=sys.stderr)
        return 1
    print(f"wrote {args.out_iso}: {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
