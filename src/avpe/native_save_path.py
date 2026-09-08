"""Platform user-data location for AVPE's native save container."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path


SAVE_FILENAME = "avpe-saves.avpesave"


def resolve_native_save_path(
    environment: Mapping[str, str],
    *,
    system: str,
    home: Path,
) -> Path:
    """Resolve the persistent native-save path without using the checkout."""
    if system == "Linux":
        configured = environment.get("XDG_DATA_HOME")
        root = Path(configured) if configured else home / ".local" / "share"
    elif system == "Darwin":
        root = home / "Library" / "Application Support"
    elif system == "Windows":
        configured = environment.get("LOCALAPPDATA") or environment.get("APPDATA")
        root = Path(configured) if configured else home / "AppData" / "Local"
    else:
        raise ValueError(f"unsupported save-path platform: {system}")
    return root / "AVPE" / SAVE_FILENAME
