"""PCSX2 configuration profiles owned by AVPE."""

from pathlib import Path


VOLATILE_UI_CONFIG = {
    "GameListTableView": None,
    "UI": frozenset({"MainWindowGeometry", "MainWindowState"}),
}


def ini_path(data_dir: Path) -> Path:
    return data_dir / "PCSX2" / "inis" / "PCSX2.ini"


def load_ini(path: Path) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    current = ""
    if path.exists():
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if line.startswith("[") and line.endswith("]"):
                current = line[1:-1]
                sections.setdefault(current, {})
            elif "=" in line and current:
                key, _, value = line.partition("=")
                sections[current][key.strip()] = value.strip()
    return sections


def timing_config_identity(path: Path) -> dict[str, dict[str, str]]:
    """Return every persisted setting except diagnosed Qt UI layout state."""

    identity: dict[str, dict[str, str]] = {}
    for section, values in load_ini(path).items():
        excluded = VOLATILE_UI_CONFIG.get(section, frozenset())
        if excluded is None:
            continue
        kept = {
            key: value
            for key, value in values.items()
            if key not in excluded
        }
        if kept:
            identity[section] = kept
    return identity


def save_ini(path: Path, sections: dict[str, dict[str, str]]) -> None:
    lines: list[str] = []
    for section, values in sections.items():
        lines.append(f"[{section}]")
        lines.extend(f"{key} = {value}" for key, value in values.items())
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".pending")
    pending.write_text("\n".join(lines))
    pending.replace(path)


def _base_sections(path: Path) -> dict[str, dict[str, str]]:
    sections = load_ini(path)
    folders = sections.setdefault("Folders", {})
    folders.setdefault("Bios", "bios")
    folders.setdefault("Snapshots", "snaps")
    folders.setdefault("Savestates", "sstates")
    folders.setdefault("MemoryCards", "memcards")
    sections.setdefault("Filenames", {}).setdefault("BIOS", "scph39001.bin")
    sections.setdefault("EmuCore", {}).setdefault("EnablePatches", "true")
    ui = sections.setdefault("UI", {})
    ui.setdefault("SettingsVersion", "1")
    ui["SetupWizardIncomplete"] = "False"
    return sections


def ensure_product_config(data_dir: Path) -> None:
    """Seed a missing product profile; never rewrite an existing user INI."""
    path = ini_path(data_dir)
    if path.exists():
        return
    sections = _base_sections(path)
    sections.setdefault("SPU2/Output", {}).update({"Backend": "Cubeb", "OutputMuted": "False"})
    sections.setdefault("EmuCore/GS", {})["Renderer"] = "-1"
    save_ini(path, sections)


def ensure_test_config(
    data_dir: Path,
    bios: Path,
    memory_card_filename: str | None = None,
) -> None:
    """Create the isolated, silent configuration used by control tests."""
    path = ini_path(data_dir)
    sections = _base_sections(path)
    sections.setdefault("SPU2/Output", {}).update({
        "Backend": "Null",
        "OutputMuted": "True",
    })
    sections.setdefault("EmuCore/GS", {})["Renderer"] = "13"
    sections.setdefault("MemoryCards", {}).update({
        "Slot1_Enable": "true" if memory_card_filename else "false",
        "Slot1_Filename": memory_card_filename or "Mcd001.ps2",
        "Slot2_Enable": "false",
    })
    save_ini(path, sections)

    bios_dir = data_dir / "PCSX2" / "bios"
    bios_dir.mkdir(parents=True, exist_ok=True)
    link = bios_dir / "scph39001.bin"
    if link.is_symlink() and link.resolve() == bios.resolve():
        return
    if link.exists() or link.is_symlink():
        raise RuntimeError(f"test BIOS link has unexpected target: {link}")
    link.symlink_to(bios.resolve())
