---
id: 20
title: Inventory AVP:E BIOS and IOP service surface
status: investigating
symptom: The AVP:E-specific BIOS/HLE service surface is not yet inventoried
state_items: S025,S026,S027,S028
tags: bios,hle,iop,inventory,re
created: 2026-08-28
updated: 2026-08-28
---

## Root cause

Existing AVPE hooks observe selected asset imports and debug registrations, but
there is no bounded structured census covering the BIOS-backed IOP lifecycle,
and no corresponding EE-kernel or firmware-service inventory.

## Current work

`NativeBiosTrace` now records EE `SYSCALL` dispatches through the shared
interpreter implementation, plus IOP imports, loadcore module registration and
release, interrupt registration, and SIF RPC registration through narrow calls
at the existing owners. It is observation-only and exposed at
`GET /bios/trace` for control-test diagnostics.

## Remaining work

Capture repeated clean traces across boot, menu, mission, save/load, and
shutdown. Add separate grounded observation seams for kernel primitives,
executable loading, timers, interrupt delivery, and IOP module loads, then
capture service results and negative paths before designing the HLE
implementation. The EE syscall dispatch seam exists but still needs runtime
phase traces and service-level interpretation.

## Resolution

Not resolved. The current census is the first partial S025 slice; it does not
establish a BIOS-free path or any S026–S028 behavior.
