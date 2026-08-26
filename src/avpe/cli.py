"""avpe CLI — doctor (preflight), provision, launch.

`doctor` performs REAL checks and refuses with actionable output on hard
blockers. Every negative prints what it looked for and what it found.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from avpe.log import log

ROOT = Path(__file__).resolve().parent.parent.parent


def load_env() -> dict[str, str]:
    path = ROOT / ".env"
    env: dict[str, str] = {}
    if not path.exists():
        log("warn", "env", f"{path} missing — copy .env.example to .env and fill it in")
        return env
    for lineno, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            log("warn", "env", f".env line {lineno} not KEY=VALUE: {line!r}")
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def check_tool(name: str, version_arg: str = "--version") -> bool:
    if shutil.which(name) is None:
        print(f"FAIL  tool {name}: not found on PATH")
        return False
    out = subprocess.run([name, version_arg], capture_output=True, text=True)
    ver = (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr) else "?"
    print(f"pass  tool {name}: {ver}")
    return True


def check_qt_prefix(deps_dir: Path) -> bool:
    """Verify the project-owned Qt build inputs from one authoritative prefix."""
    header = deps_dir / "include" / "QtCore" / "qglobal.h"
    config = deps_dir / "lib" / "cmake" / "Qt6" / "Qt6Config.cmake"
    if header.is_file() and config.is_file():
        print(f"pass  self-built Qt/deps prefix: {deps_dir} (headers + CMake config)")
        return True
    print(f"FAIL  self-built Qt prefix incomplete: header={header.is_file()} "
          f"cmake_config={config.is_file()} — run the pcsx2 "
          ".github/workflows/scripts/linux/build-dependencies-qt.sh script")
    return False


def doctor() -> int:
    failures = 0
    env = load_env()

    # 1. Game CHD
    chd = env.get("AVPE_CHD", "")
    if not chd:
        print("FAIL  AVPE_CHD not set in .env — cannot locate the game disc")
        failures += 1
    elif not Path(chd).exists():
        print(f"FAIL  AVPE_CHD points at a nonexistent file: {chd}")
        failures += 1
    else:
        size_mb = Path(chd).stat().st_size / 1e6
        print(f"pass  game CHD: {chd} ({size_mb:.0f} MB)")

    # 2. BIOS dir
    bios_dir = env.get("AVPE_BIOS_DIR", "")
    bins: list[Path] = []
    if not bios_dir:
        print("FAIL  AVPE_BIOS_DIR not set in .env")
        failures += 1
    elif not Path(bios_dir).is_dir():
        print(f"FAIL  AVPE_BIOS_DIR is not a directory: {bios_dir}")
        failures += 1
    else:
        candidates = list(Path(bios_dir).glob("*.bin")) + list(Path(bios_dir).glob("*.BIN")) + \
            list(Path(bios_dir).glob("*.rom*"))
        bins = [p for p in candidates if p.stat().st_size >= 2_000_000]
        if not bins:
            print(f"FAIL  BIOS dir {bios_dir} scanned: {len(candidates)} rom-ish files, "
                  f"0 of plausible PS2 BIOS size (>=2 MB)")
            failures += 1
        else:
            names = ", ".join(p.name for p in sorted(bins))
            print(f"pass  BIOS dir {bios_dir}: {len(bins)} usable ROMs: {names}")

    # 3. Dependency manifest + clone state
    deps_path = ROOT / "deps.toml"
    deps = tomllib.loads(deps_path.read_text()) if deps_path.exists() else {}
    pcx = deps.get("pcsx2", {})
    clone = ROOT / "thirdparty" / "pcsx2"
    if not clone.is_dir():
        print(f"FAIL  PCSX2 clone missing at thirdparty/pcsx2 — run: ./run.sh provision")
        failures += 1
    else:
        head = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
        rev = pcx.get("rev", "")
        if rev and head != rev:
            print(f"WARN  pcsx2 HEAD {head[:12]} != pinned rev {rev[:12]} — fork commits expected on top")
        else:
            print(f"pass  pcsx2 clone HEAD {head[:12]} matches pin")

    # 4. Built binary
    binary = ROOT / "scratch" / "build" / "bin" / "pcsx2-qt"
    deps_dir = ROOT / "scratch" / "deps"
    if binary.exists():
        print(f"pass  built binary: {binary}")
    else:
        print(f"FAIL  no built PCSX2 at {binary} — configure+build required before launch")
        failures += 1
    if not check_qt_prefix(deps_dir):
        failures += 1

    # 5. Toolchain
    for tool in ("cmake", "clang++", "ninja", "ccache", "chdman", "git"):
        if not check_tool(tool):
            failures += 1

    # 6. SDL3 (PCSX2 input/audio layer)
    sdl3 = subprocess.run(["pkg-config", "--modversion", "sdl3"], capture_output=True, text=True)
    if sdl3.returncode == 0:
        print(f"pass  SDL3: {sdl3.stdout.strip()}")
    else:
        print("FAIL  SDL3 development files not found via pkg-config — Fedora: sudo dnf install SDL3-devel")
        failures += 1

    # 7. Ghidra (RE phase)
    ghidra = shutil.which("analyzeHeadless") or next(
        (p for p in sorted(Path.home().glob("dev/ghidra_*/support/analyzeHeadless"))), None)
    if ghidra:
        print(f"pass  Ghidra headless: {ghidra}")
    else:
        print("WARN  Ghidra analyzeHeadless not found — needed only for the RE phase")

    print(f"\ndoctor: {failures} blocker(s)" if failures else "\ndoctor: all clear")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="avpe")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("doctor", help="preflight checks with actionable refusals")
    sub.add_parser("launch", help="boot the user-facing AVPE host")

    args = parser.parse_args(argv)
    if args.cmd in (None, "launch"):
        from avpe.launch import launch
        env = load_env()
        chd = env.get("AVPE_CHD", "")
        if not chd:
            log("error", "cli", "AVPE_CHD not set in .env")
            return 1
        if args.cmd is None:
            log("info", "cli", "no command given -> windowed launch")
        return launch(chd)
    if args.cmd == "doctor":
        return doctor()
    parser.error(f"unknown command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
