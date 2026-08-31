"""avpe CLI — doctor (preflight), provision, prepare, launch.

`doctor` performs REAL checks and refuses with actionable output on hard
blockers. Every negative prints what it looked for and what it found.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from avpe.build import BuildError, prepare_product
from avpe.dependency_prefix import dependency_prefix_complete, dependency_prefix_error
from avpe.dependencies import inspect_submodule, provision_submodules
from avpe.log import log
from avpe.native_assets import NativeAssetError, provision_native_assets

ROOT = Path(__file__).resolve().parent.parent.parent
NATIVE_ASSET_DIR = ROOT / "scratch" / "native-assets"


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
    """Report whether the project-owned dependency prefix is complete."""
    if dependency_prefix_complete(deps_dir):
        print(f"pass  self-built Qt/deps prefix: {deps_dir} (headers + CMake config)")
        return True
    print(f"FAIL  {dependency_prefix_error(deps_dir)}")
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

    # 3. Tracked PCSX2 submodule state
    submodule = inspect_submodule(ROOT)
    if submodule.expected_revision is None:
        print("FAIL  PCSX2 is not registered as the thirdparty/pcsx2 submodule")
        failures += 1
    elif submodule.checkout_revision is None:
        print("FAIL  PCSX2 submodule is not initialized — run: ./run.sh provision")
        failures += 1
    elif not submodule.is_ready:
        print(
            "FAIL  pcsx2 submodule HEAD "
            f"{submodule.checkout_revision[:12]} != tracked gitlink "
            f"{submodule.expected_revision[:12]} — run: ./run.sh provision"
        )
        failures += 1
    else:
        print(
            "pass  pcsx2 submodule HEAD "
            f"{submodule.checkout_revision[:12]} matches tracked gitlink"
        )

    # 4. Built binary
    binary = ROOT / "build" / "bin" / "avpe"
    deps_dir = ROOT / "build" / "deps"
    if binary.exists():
        print(f"pass  built binary: {binary}")
    else:
        print(f"FAIL  no built AVPE frontend at {binary} — run ./run.sh prepare")
        failures += 1
    if not check_qt_prefix(deps_dir):
        failures += 1

    # 5. Toolchain
    for tool in ("cmake", "ninja", "ccache", "chdman", "git"):
        if not check_tool(tool):
            failures += 1

    configured_cxx = os.environ.get("CXX")
    cxx_candidates = (configured_cxx,) if configured_cxx else ("c++", "g++", "clang++")
    cxx = next((candidate for candidate in cxx_candidates if candidate and shutil.which(candidate)), None)
    if cxx is None:
        print("FAIL  no C++ compiler found (supported: GCC, Clang, or AppleClang)")
        failures += 1
    elif not check_tool(cxx):
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
    sub.add_parser("provision", help="initialize the tracked dependency submodules")
    sub.add_parser("prepare", help="provision and build the standalone AVPE product")
    sub.add_parser("assets", help="provision and validate the PC-native asset store")
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
        try:
            prepare_product(ROOT)
        except BuildError as error:
            log("error", "prepare", str(error))
            return 1
        return launch(chd)
    if args.cmd == "doctor":
        return doctor()
    if args.cmd == "provision":
        if not provision_submodules(ROOT):
            log("error", "provision", "submodule initialization failed")
            return 1
        submodule = inspect_submodule(ROOT)
        if not submodule.is_ready:
            log("error", "provision", "PCSX2 checkout does not match the tracked gitlink")
            return 1
        log("info", "provision", f"PCSX2 ready at {submodule.checkout_revision[:12]}")
        return 0
    if args.cmd == "prepare":
        try:
            binary = prepare_product(ROOT)
        except BuildError as error:
            log("error", "prepare", str(error))
            return 1
        log("info", "prepare", f"AVPE product ready at {binary}")
        return 0
    if args.cmd == "assets":
        chd = load_env().get("AVPE_CHD", "")
        if not chd:
            log("error", "assets", "AVPE_CHD not set in .env")
            return 1
        try:
            root = provision_native_assets(Path(chd), NATIVE_ASSET_DIR)
        except (NativeAssetError, OSError) as error:
            log("error", "assets", str(error))
            return 1
        log("info", "assets", f"validated native store: {root}")
        return 0
    parser.error(f"unknown command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
