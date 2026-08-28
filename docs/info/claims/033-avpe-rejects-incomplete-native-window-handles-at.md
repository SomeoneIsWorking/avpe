---
id: C033
kind: claim
status: holds
created: 2026-08-28
tags: host,presentation
depends: thirdparty/pcsx2/pcsx2-avpe/NativeWindow.cpp#GetInfoFor, thirdparty/pcsx2/pcsx2-avpe/NativeWindow.h#HasRequiredNativeHandles, thirdparty/pcsx2/tests/ctest/core/avpe_native_window_tests.cpp#NativeWindowHandlesTest
---

## Claim

AVPE rejects incomplete native window handles at acquisition

## Evidence

NativeWindow::GetInfoFor now applies one shared handle-validity predicate before returning WindowInfo. Surfaceless accepts no handles, X11 and Wayland require display plus window/surface handles, and Win32/MacOS require a window handle. The production avpe target built with Clang and the normal verifier ran 22 production C++ tests, including three NativeWindowHandlesTest cases, plus 119 Python tests, clang-format, and 46 clang-tidy translation units.

## What would falsify it

NativeWindow::GetInfoFor returns an engaged non-surfaceless WindowInfo with a required null handle, or the predicate tests no longer distinguish valid and invalid platform handle combinations
