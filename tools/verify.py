#!/usr/bin/env python3
"""Run AVPE's non-windowed source and unit verification gates."""

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "scratch" / "build"
COMPILE_COMMANDS = BUILD_DIR / "compile_commands.json"

CPP_SOURCES = (
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/AVPE.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/EECallShuttle.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2-qt/AVPE/HostWindow.cpp",
)
CPP_HEADERS = (
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/AVPE.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/EECallShuttle.h",
    ROOT / "thirdparty/pcsx2/pcsx2-qt/AVPE/HostWindow.h",
)


def require_tool(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise RuntimeError(f"required verifier tool is missing: {name}")
    return executable


def run(label: str, argv: list[str]) -> None:
    print(f"verify: {label}", flush=True)
    subprocess.run(argv, cwd=ROOT, check=True)


def main() -> int:
    missing_sources = [
        path for path in (*CPP_SOURCES, *CPP_HEADERS) if not path.is_file()
    ]
    if missing_sources:
        print(
            "verify: missing AVPE source: "
            + ", ".join(str(path) for path in missing_sources),
            file=sys.stderr,
        )
        return 2
    if not COMPILE_COMMANDS.is_file():
        print(
            f"verify: missing {COMPILE_COMMANDS}; configure CMake with "
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
            file=sys.stderr,
        )
        return 2

    try:
        clang_format = require_tool("clang-format")
        clang_tidy = require_tool("clang-tidy")
        run(
            "Python unit and structure tests",
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_*.py",
                "-v",
            ],
        )
        run(
            "clang-format",
            [
                clang_format,
                "--dry-run",
                "--Werror",
                *(str(path) for path in (*CPP_SOURCES, *CPP_HEADERS)),
            ],
        )
        run(
            "clang-tidy",
            [clang_tidy, "-p", str(BUILD_DIR), "--quiet", *(str(path) for path in CPP_SOURCES)],
        )
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"verify: FAIL: {error}", file=sys.stderr)
        return 1

    print("verify: all non-windowed gates passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
