#!/bin/sh
# AVPE launcher — slim shim. All logic lives in Python (uv-locked).
set -eu
cd "$(dirname "$0")"
exec uv run --frozen avpe launch "$@"
