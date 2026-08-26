"""Single configurable logger for the AVPE python side.

One call site, one line per call. Level from AVPE_LOG (debug|info|warn|error),
default info. Never wrap call sites in `if` — the logger owns the gate.
"""

import os
import sys

_LEVELS = {"debug": 10, "info": 20, "warn": 30, "error": 40}
_threshold = _LEVELS.get(os.environ.get("AVPE_LOG", "info").lower(), 20)


def log(level: str, comp: str, msg: str) -> None:
    if _LEVELS[level] < _threshold:
        return
    stream = sys.stderr if level in ("warn", "error") else sys.stdout
    print(f"[avpe][{level}][{comp}] {msg}", file=stream, flush=True)
