#!/usr/bin/env python3
"""Run AVPE's hosted, asset-free build and verification gate."""

import sys
import subprocess
from pathlib import Path

from avpe.ci import CiError, verify_host


ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    try:
        binary = verify_host(ROOT)
    except CiError as error:
        print(f"ci: FAIL: {error}", file=sys.stderr)
        return 2
    except (RuntimeError, subprocess.SubprocessError) as error:
        print(f"ci: FAIL: {error}", file=sys.stderr)
        return 1
    print(f"ci: verified asset-free product boundary: {binary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
