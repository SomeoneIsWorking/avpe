---
id: 3
title: Replace PCSX2 product window with AVPE host shell
status: verifying
symptom: normal product and prior agent tests expose PCSX2's generic game render window instead of an AVPE-owned native shell
state_items: S013,S018,S020
tags: host,pcsx2,presentation,rmlui
created: 2026-08-26
updated: 2026-08-27
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
the product target. The Clang link and offscreen configuration check pass, but
no visible product test was run because agent tests must remain windowless.

## Verification

- Operator-only desktop acceptance through `./run.sh` shows exactly the
  AVPE-owned top-level window. Agent verification must never invoke this route.
- PCSX2's generic main/render/settings UI is absent from the product link graph.
- Window resize, fullscreen, focus loss/recovery, and shutdown exercise the
  AVPE host lifecycle.
- Optional RmlUi diagnostics can compose over a live frame without becoming
  the shipping options path.
- The dedicated control-test runner remains genuinely surfaceless and silent.
