#!/usr/bin/env python3
"""Run AVPE's non-windowed source and unit verification gates."""

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "scratch" / "build"
COMPILE_COMMANDS = BUILD_DIR / "compile_commands.json"
CORE_TEST = BUILD_DIR / "bin" / "core_test"

CPP_SOURCES = (
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/AVPE.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/EECallShuttle.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/GuestObjects.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeAssetByteTrace.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeAssetStore.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeAssets.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeLoadTiming.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeInput.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeMenuInput.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativePointerMotion.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/Interpreter.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/IopBios.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/x86/ix86-32/iR5900.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2-avpe/EmulationThread.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2-avpe/HostServices.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2-avpe/HostInputRouter.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2-avpe/HostWindow.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2-avpe/Main.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2-avpe/NativeWindow.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2-avpe/RenderSurface.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2-avpe/Runtime.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2-avpe/Settings.cpp",
    ROOT / "thirdparty/pcsx2/tests/ctest/core/avpe_native_asset_store_tests.cpp",
)
CPP_HEADERS = (
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/AVPE.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/EECallShuttle.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/GuestObjects.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeAssetByteTrace.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeAssetStore.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeAssets.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeLoadTiming.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeInput.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeMenuInput.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativePointerMotion.h",
    ROOT / "thirdparty/pcsx2/pcsx2-avpe/EmulationThread.h",
    ROOT / "thirdparty/pcsx2/pcsx2-avpe/HostBackend.h",
    ROOT / "thirdparty/pcsx2/pcsx2-avpe/HostInputRouter.h",
    ROOT / "thirdparty/pcsx2/pcsx2-avpe/HostWindow.h",
    ROOT / "thirdparty/pcsx2/pcsx2-avpe/NativeWindow.h",
    ROOT / "thirdparty/pcsx2/pcsx2-avpe/RenderSurface.h",
    ROOT / "thirdparty/pcsx2/pcsx2-avpe/Runtime.h",
    ROOT / "thirdparty/pcsx2/pcsx2-avpe/Settings.h",
)
CORE_SCOPED_SOURCES = {
    ROOT / "thirdparty/pcsx2/pcsx2/IopBios.cpp": (
        (1, 13), (265, 312), (415, 438), (604, 708), (843, 936),
        (992, 1059), (1460, 1505)),
    ROOT / "thirdparty/pcsx2/pcsx2/Interpreter.cpp": (
        (1, 10), (22, 35), (563, 620), (688, 720)),
    ROOT / "thirdparty/pcsx2/pcsx2/x86/ix86-32/iR5900.cpp": (
        (1, 10), (47, 51), (398, 410), (779, 788), (2_205, 2_220)),
}
FULL_FORMAT_SOURCES = tuple(
    path for path in CPP_SOURCES if path not in CORE_SCOPED_SOURCES
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
            "native asset store C++ test build",
            ["cmake", "--build", str(BUILD_DIR), "--target", "core_test", "-j2"],
        )
        run(
            "native asset store production-path tests",
            [str(CORE_TEST), "--gtest_filter=NativeAssetStoreTest.*"],
        )
        run(
            "clang-format",
            [
                clang_format,
                "--dry-run",
                "--Werror",
                *(str(path) for path in (*FULL_FORMAT_SOURCES, *CPP_HEADERS)),
            ],
        )
        for path, ranges in CORE_SCOPED_SOURCES.items():
            run(
                f"clang-format touched ranges in {path.name}",
                [
                    clang_format,
                    "--dry-run",
                    "--Werror",
                    *(f"--lines={start}:{end}" for start, end in ranges),
                    str(path),
                ],
            )
        line_filter = [
            {
                "name": str(path),
                "lines": [[1, 10000]],
            }
            for path in (*FULL_FORMAT_SOURCES, *CPP_HEADERS)
        ] + [
            {
                "name": str(path),
                "lines": [list(line_range) for line_range in ranges],
            }
            for path, ranges in CORE_SCOPED_SOURCES.items()
        ]
        run(
            "clang-tidy",
            [
                clang_tidy,
                "-p",
                str(BUILD_DIR),
                "--quiet",
                f"--line-filter={json.dumps(line_filter)}",
                *(str(path) for path in CPP_SOURCES),
            ],
        )
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"verify: FAIL: {error}", file=sys.stderr)
        return 1

    print("verify: all non-windowed gates passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
