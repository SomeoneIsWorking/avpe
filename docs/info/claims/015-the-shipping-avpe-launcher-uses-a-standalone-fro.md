---
id: C015
kind: claim
status: holds
created: 2026-08-27
tags: build,host
depends: thirdparty/pcsx2/pcsx2-avpe/CMakeLists.txt, thirdparty/pcsx2/pcsx2-avpe/Runtime.cpp#Runtime, src/avpe/launch.py#build_argv
---

## Claim

The shipping AVPE launcher uses a standalone frontend linked to the PCSX2 emulation-core library, with no pcsx2-qt GUI sources or libraries in the product target.

## Evidence

Clang built scratch/build/bin/avpe and pcsx2-qt independently; Ninja's avpe link command contains pcsx2-avpe objects plus libpcsx2.a and no pcsx2-qt, MainWindow, DisplayWidget, GameList, Debugger, settings dialogs, or KDDockWidgets. QT_QPA_PLATFORM=offscreen with desktop variables removed ran avpe --test-config successfully without constructing Runtime/HostWindow. The 18-test structural suite and full clang-format/clang-tidy verifier passed; the separate five-second pcsx2-qt oracle run reported surfaceless and null-muted.

## What would falsify it

The avpe target links any pcsx2-qt GUI object/library, the launcher selects pcsx2-qt or -avpe-host again, the offscreen configuration check creates a surface, or the structural boundary test stops detecting a forbidden dependency.
