#!/usr/bin/env zsh
# AVPE launcher — slim shim. All logic lives in Python (uv-locked).
set -euo pipefail
cd "$(dirname "$0")"
exec uv run --frozen avpe "$@"
