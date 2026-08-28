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
interpreter implementation, including their four argument registers and
post-dispatch signed `v0` result, EE/IOP exception entry, plus IOP imports,
loadcore module registration and release, interrupt registration, and SIF RPC
registration. EE and IOP counter target/overflow paths now record the counter
state, cycle, and whether the interrupt was delivered. All observations use
narrow calls at the existing owners, remain observation-only, and are exposed at
`GET /bios/trace` for control-test diagnostics.

The surfaceless runner now captures the sink atomically at the verified
`Running` boundary through `POST /bios/trace/capture`. Three repeated clean
boots produced the same 28-event slice (20 module registrations, 7 IOP
exceptions, 1 IOP timer event, zero overflow), proving the boot boundary is
repeatable. The capture is deliberately labelled `clean_boot_to_running`; it
does not claim to cover later EE or game-service activity.

## Remaining work

Capture repeated clean traces across boot, menu, mission, save/load, and
shutdown. Add a separate grounded observation seam for remaining interrupt
delivery, kernel primitives, executable loading, and IOP module loads, then
capture their service results and negative paths before designing the HLE
implementation. The EE syscall result boundary now exists but still needs
runtime phase traces and service-level interpretation.

## Resolution

Not resolved. The current census is the first partial S025 slice; it does not
establish a BIOS-free path or any S026–S028 behavior.
