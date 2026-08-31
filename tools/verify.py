#!/usr/bin/env python3
"""Run AVPE's non-windowed source and unit verification gates."""

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
COMPILE_COMMANDS = BUILD_DIR / "compile_commands.json"
CORE_TEST = BUILD_DIR / "bin" / "core_test"

CPP_SOURCES = (
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/AVPE.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/EECallShuttle.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/GuestObjects.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/LoadTimingPoint.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeAssetByteTrace.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeBiosEventStore.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeBiosTrace.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeEeExecutionHooks.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeIopExecutionHooks.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeIopReturnSites.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeHostYield.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeAssetCache.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeAssetFile.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeAssetStateSnapshot.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeAssetStore.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeAssets.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeCdvdCompletion.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeGuestReset.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeLoadTiming.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeMissionLoadTiming.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeInput.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeInputData.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeCameraInput.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeCameraRoute.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/HttpJson.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeMenuInput.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeMenuRoute.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativePointerMotion.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/Counters.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/Interpreter.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/IopBios.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/IopCounters.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/R5900OpcodeImpl.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/R5900.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/R3000A.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/R3000AInterpreter.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/x86/iR3000A.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/SaveState.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/VMManager.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/x86/ix86-32/iR5900.cpp",
    ROOT / "thirdparty/pcsx2/pcsx2/x86/ix86-32/iR5900Jump.cpp",
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
    ROOT / "thirdparty/pcsx2/tests/ctest/core/avpe_native_cdvd_completion_tests.cpp",
    ROOT / "thirdparty/pcsx2/tests/ctest/core/avpe_native_bios_trace_tests.cpp",
    ROOT / "thirdparty/pcsx2/tests/ctest/core/avpe_native_window_tests.cpp",
)
CPP_HEADERS = (
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/AVPE.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/EECallShuttle.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/GuestObjects.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/LoadTimingPoint.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeAssetByteTrace.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeBiosEventStore.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeBiosTrace.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeEeExecutionHooks.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeIopExecutionHooks.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeIopReturnSites.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeHostYield.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeAssetCache.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeAssetFile.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeAssetStateSnapshot.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeAssetStore.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeAssets.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeCdvdCompletion.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeGuestReset.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeLoadTiming.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeMissionLoadTiming.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeInput.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeInputData.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeCameraInput.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeCameraRoute.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/HttpJson.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeMenuInput.h",
    ROOT / "thirdparty/pcsx2/pcsx2/AVPE/NativeMenuRoute.h",
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
        (1, 35), (265, 312), (415, 708), (823, 936),
        (992, 1120), (1428, 1498), (1510, 1565), (1600, 1819)),
    ROOT / "thirdparty/pcsx2/pcsx2/IopCounters.cpp": ((1, 16), (207, 240)),
	ROOT / "thirdparty/pcsx2/pcsx2/Counters.cpp": ((1, 20), (488, 494), (682, 723)),
	ROOT / "thirdparty/pcsx2/pcsx2/R5900OpcodeImpl.cpp": (
		(1, 18), (910, 925), (1059, 1063), (1196, 1201), (1206, 1210)),
    ROOT / "thirdparty/pcsx2/pcsx2/R5900.cpp": ((1, 18), (96, 99)),
    ROOT / "thirdparty/pcsx2/pcsx2/Interpreter.cpp": (
        (1, 10), (22, 35), (177, 182), (563, 620), (688, 720)),
    ROOT / "thirdparty/pcsx2/pcsx2/R3000A.cpp": ((1, 10), (50, 57), (64, 69)),
    ROOT / "thirdparty/pcsx2/pcsx2/R3000AInterpreter.cpp": ((1, 15), (261, 264)),
    ROOT / "thirdparty/pcsx2/pcsx2/x86/iR3000A.cpp": (
        (1, 15), (705, 765), (1685, 1695)),
    ROOT / "thirdparty/pcsx2/pcsx2/SaveState.cpp": (
        (90, 105), (315, 325), (1080, 1130), (1140, 1165), (1175, 1215)),
    ROOT / "thirdparty/pcsx2/pcsx2/VMManager.cpp": (
        (1, 10), (1690, 1710), (2335, 2400)),
	ROOT / "thirdparty/pcsx2/pcsx2/x86/ix86-32/iR5900.cpp": (
		(1, 10), (47, 51), (398, 410), (779, 805), (1_698, 1_707),
		(2_205, 2_220), (2_354, 2_357)),
    ROOT / "thirdparty/pcsx2/pcsx2/x86/ix86-32/iR5900Jump.cpp": (
        (1, 10), (75, 82)),
}
CORE_SCOPED_HEADERS = {
    ROOT / "thirdparty/pcsx2/pcsx2/IopBios.h": ((64, 90),),
    ROOT / "thirdparty/pcsx2/pcsx2/SaveState.h": (
        (20, 32), (70, 100), (345, 358)),
    ROOT / "thirdparty/pcsx2/pcsx2/VMManager.h": ((210, 220),),
}
FULL_FORMAT_SOURCES = tuple(
    path for path in CPP_SOURCES if path not in CORE_SCOPED_SOURCES
)
FULL_FORMAT_HEADERS = tuple(
    path for path in CPP_HEADERS if path not in CORE_SCOPED_HEADERS
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
        path
        for path in (*CPP_SOURCES, *CPP_HEADERS, *CORE_SCOPED_HEADERS)
        if not path.is_file()
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
            "native AVPE production-path tests",
            [
                str(CORE_TEST),
                "--gtest_filter=NativeAssetStoreTest.*:NativeCdvdCompletionTest.*:NativeBiosTraceTest.*:NativeWindowHandlesTest.*",
            ],
        )
        run(
            "clang-format",
            [
                clang_format,
                "--dry-run",
                "--Werror",
                *(str(path) for path in (*FULL_FORMAT_SOURCES, *FULL_FORMAT_HEADERS)),
            ],
        )
        for path, ranges in (*CORE_SCOPED_SOURCES.items(), *CORE_SCOPED_HEADERS.items()):
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
            for path in (*FULL_FORMAT_SOURCES, *FULL_FORMAT_HEADERS)
        ] + [
            {
                "name": str(path),
                "lines": [list(line_range) for line_range in ranges],
            }
            for path, ranges in (*CORE_SCOPED_SOURCES.items(), *CORE_SCOPED_HEADERS.items())
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
