---
id: 20
title: Inventory AVP:E BIOS and IOP service surface
status: investigating
symptom: The AVP:E-specific BIOS/HLE service surface is not yet inventoried
state_items: S025,S026,S027,S028
tags: bios,hle,iop,inventory,re
created: 2026-08-28
updated: 2026-09-12
---

## Root cause

The project began with only selected asset-import/debug hooks and no bounded
firmware census. The remaining root gap is now narrower: the v6 mission,
game-save, and game-load census
has grounded EE BIOS and IOP oracle return owners with ABI-aware result
validity. Schema v6 captures declared 64-bit EE results without truncation and
coalesces changing results into bounded summaries. The ordinary clean boot has
exercised `GsPutIMR`, and the normal Save Game path now completes through
`CProfile::SaveGame`, and the matching normal Load Game path completes through
`CProfile::LoadGame`. Static reachability excludes `GsGetIMR`'s dead
screen-capture helper from the normal-title inventory; stable title completion,
the guest-owned shutdown boundary, runtime operations beyond the current
boot/archive/save/load slices, and service negative paths are still absent.
One mission slice cannot substitute for the complete required firmware contract.

## Current work

`NativeBiosTrace` v7 retains the v3 EE `SYSCALL` contract through the shared
interpreter implementation, including their four argument registers and
whether PCSX2 returned directly or dispatched into the BIOS. Return-capable
BIOS entries pair by guest stack pointer and exact post-syscall PC. A ps2sdk-
grounded disposition table separates captured signed 32-bit results, returned
void calls, unobserved result types, and non-returning context/process/thread
transfers. Recognized HLE/debug IOP imports snapshot arguments, stack pointer,
and caller return PC before dispatch. Handled HLE carries its immediate result.
Oracle fallback queues a bounded frame, registers that exact caller return
block, and pairs the eventual signed `v0` by stack pointer and return PC through
`NativeIopExecutionHooks`. The recompiler instruments only registered return
blocks; the interpreter scans the registry only while an oracle call is pending.
The census also records actual EE/IOP exception transitions,
loadcore module registration and release, interrupt registration, and SIF RPC
registration. EE and IOP counter target/overflow paths now record the counter
state, cycle, and whether the counter source asserted an interrupt. All observations use
narrow calls at the existing owners, remain observation-only, and are exposed at
`GET /bios/trace` for control-test diagnostics. Repeated import, syscall,
exception, and timer identities are coalesced with occurrence counts. Result-
bearing identities additionally retain first, last, minimum, maximum, and
change count, preventing a changing hot result from exhausting capacity. Every
reached IOP import is now admitted to the census while it is enabled, including
imports without an HLE or debug handler; unresolved names are recorded as
`unknown` with their library and ordinal, while dispatch remains on the
original oracle path.

## Remaining work

- Firmware services beyond the boot, mission-archive, game-save, game-load,
  slot-enumeration, guest-reset, and movie slices are not yet inventoried.
- Stable title completion and the guest-owned shutdown boundary are unobserved.
- Service negative paths (unobserved result types, failing and busy services)
  are not exercised for the inventoried contracts.
- Clock, counter, and interrupt relationships in the title's own state machine
  remain unproven.
- `GsGetIMR` is statically excluded from the normal-title path by a dead
  screen-capture helper; that exclusion is not runtime-confirmed.

## Resolution

Not resolved. The current census is the first partial S025 slice; it does not
establish a BIOS-free path or any S026–S028 behavior.
