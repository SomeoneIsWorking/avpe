---
id: 3
title: Replace PCSX2 product window with AVPE host shell
status: investigating
symptom: normal product and prior agent tests expose PCSX2's generic game render window instead of an AVPE-owned native shell
state_items: S013,S018,S020
tags: host,pcsx2,presentation,rmlui
created: 2026-08-26
updated: 2026-08-26
---

## Root cause

The product launcher starts PCSX2's Qt host directly, so PCSX2's generic
`MainWindow` / `DisplaySurface` owns the visible product window. Hiding the
emulator UI with `-nogui` does not change that ownership and cannot provide an
AVPE-native shell.

## Required change

Use an AVPE-owned top-level host that exclusively receives PCSX2's presentation
signals and embeds the low-level render surface. It owns presentation, input
focus/routing, fullscreen and resize transitions, RmlUi composition, and
product shutdown. The generic `MainWindow` remains hidden and administrative;
future RmlUi composition belongs behind a narrow fork-side presentation bridge.
Interfaces must remain separable so a later standalone executable can replace
the administrative Qt host without rewriting product modules.

## Current implementation

`AVPE::HostWindow` owns the top-level product window and the five render-window
signals in `-avpe-host` mode. The default launcher requires that mode. The
Clang build and offscreen capability check pass, but no visible product test was
run because agent tests must remain windowless.

## Verification

- Operator-only desktop acceptance through `./run.sh` shows exactly the
  AVPE-owned top-level window. Agent verification must never invoke this route.
- PCSX2's generic main/render/settings UI is not mapped or reachable.
- Window resize, fullscreen, focus loss/recovery, and shutdown exercise the
  AVPE host lifecycle.
- RmlUi can compose over a live frame and receive keyboard/mouse input.
- The dedicated control-test runner remains genuinely surfaceless and silent.
