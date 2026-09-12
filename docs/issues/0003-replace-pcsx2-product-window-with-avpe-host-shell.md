---
id: 3
title: Replace PCSX2 product window with AVPE host shell
status: verifying
symptom: normal product and prior agent tests expose PCSX2's generic game render window instead of an AVPE-owned native shell
state_items: S013,S018,S020
tags: host,pcsx2,presentation,rmlui
created: 2026-08-26
updated: 2026-09-04
---

## Root cause

The product launcher starts PCSX2's Qt host directly, so PCSX2's generic
`MainWindow` / `DisplaySurface` owns the visible product window. Hiding the
emulator UI with `-nogui` does not change that ownership and cannot provide an
AVPE-native shell.

## Required change

Use the PCSX2 emulation core as a library behind an AVPE-owned executable, as a
frontend such as LRPS2/libretro does. AVPE owns presentation, input routing,
fullscreen and resize transitions, host settings ownership, and
product shutdown. `pcsx2-qt` remains only the diagnostic/oracle frontend and
must not be linked into or instantiated by the product.

## Current implementation

The `avpe` executable in `pcsx2-avpe/` links the `PCSX2` core library and owns
its CPU thread, VM lifecycle, settings, host callbacks, native render surface,
window, and PC input policy. The product launcher invokes that executable
directly. A structural regression rejects PCSX2 GUI sources or libraries in
the product target. The Clang link and offscreen configuration check pass.

The standalone settings owner must explicitly populate `ImGuiManager`'s text
font list from its bundled Roboto resource before GS startup. Without that
step, `AddTextFont()` necessarily returns null, renderer initialization fails,
and the normal launcher exits before it can boot the game. With the font list
initialized and batch mode reserved for the surfaceless control route, a normal
launcher run kept `avpe` alive through GS CRTC setup and multiple game FMVs.
The current isolated-display evidence for visible ownership, fullscreen, and
title keyboard delivery is recorded under S020 in `docs/project-state.md`.

## Verification

### Note (2026-08-28)

`NativeWindow::GetInfoFor()` now validates the platform-native handles before
returning an engaged `WindowInfo`. X11 and Wayland require both display and
window/surface handles; Win32 and MacOS require a window handle; Surfaceless
remains valid without handles. The pure predicate is covered by three
no-window C++ tests, and the existing renderer acquisition path still receives
`std::nullopt` for invalid resources. Xvfb and nested KWin/Xwayland runs now
cover boot, resize, fullscreen, focus acquisition, close, and failed-boot exit.
Mouse delivery and focus loss/recovery remain open.

- The zero-argument `./run.sh` opens the AVPE-owned top-level window; isolated
  diagnostic runs exercise its event and presentation boundaries.
- PCSX2's generic main/render/settings UI is absent from the product link graph.
- Focus loss/recovery and product mouse delivery still need direct coverage.
- Optional RmlUi diagnostics can compose over a live frame without becoming
  the shipping options path.
- The dedicated control-test runner remains genuinely surfaceless and silent.
