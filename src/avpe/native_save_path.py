"""Platform user-data location for AVPE's native save container."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path


SAVE_FILENAME = "avpe-saves.avpesave"


def resolve_native_data_root(
    environment: Mapping[str, str],
    *,
    system: str,
    home: Path,
) -> Path:
    """Resolve AVPE's persistent user-data root without using the checkout."""
    if system == "Linux":
        configured = environment.get("XDG_DATA_HOME")
        if configured and not Path(configured).is_absolute():
            raise ValueError("XDG_DATA_HOME must be an absolute path for AVPE user data")
        root = Path(configured) if configured else home / ".local" / "share"
    elif system == "Darwin":
        root = home / "Library" / "Application Support"
    elif system == "Windows":
        configured = environment.get("LOCALAPPDATA") or environment.get("APPDATA")
        root = Path(configured) if configured else home / "AppData" / "Local"
    else:
        raise ValueError(f"unsupported save-path platform: {system}")
    return root / "AVPE"


def resolve_native_save_path(
    environment: Mapping[str, str],
    *,
    system: str,
    home: Path,
) -> Path:
    """Resolve the native container inside the product's user-data root."""
    return resolve_native_data_root(environment, system=system, home=home) / SAVE_FILENAME
