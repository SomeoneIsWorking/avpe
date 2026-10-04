---
id: 20
title: Inventory AVP:E BIOS and IOP service surface
status: investigating
symptom: The AVP:E-specific BIOS/HLE service surface is not yet inventoried
state_items: S025,S026,S027,S028
tags: bios,hle,iop,inventory,re
created: 2026-08-28
updated: 2026-10-04
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

## Shutdown boundary: observer grounded, probe cannot reach Quit

The guest-owned shutdown boundary stays unobserved, and the cause is now diagnosed rather than
assumed.

`NativeShellShutdownBoundary` correctly locates its targets from a live pause-menu state:
`CShell::Quit` at `0x0016F9C0`, the `CShell::MainLoop` return at `0x0016F9B0`, and the shell
singleton at `0x00497850`. In the pointer phase both PCs are reported but stay `null`, so the
observer is armed and grounded while the guest never executes them, and the phase fails with
`HTTP 504` and every boundary field false.

Neither probe phase can drive the game to invoke Quit, for the same underlying reason. In the
pad-driven phase the focus walk from the mission pause menu behaves like this:

```text
step 0     action 0x95DF2577  object 0x0150B370
steps 1-6  action 0xCA788CFB  six distinct objects, 0x0150BE50 .. 0x0151A000
step 7     action 0xCA788CFB  object 0x0151A000  (repeat of step 6)
```

DOWN advances through seven distinct items and then stops rather than wrapping, so the walk reaches
the last item and then trips its "repeated a non-target focus" guard. Two things are wrong with the
match: six of the seven items report the *same* `focused_item_action`, so that field does not
uniquely identify an item in this menu, and the final item reports `0xCA788CFB`, which never equals
the `QUIT_GAME_ACTION` constant `0x3CF57571` the phase requires.

The walk does appear to reach the last item, which in this menu is Quit, but the action-hash match
cannot recognise it. Closing this needs either a correct per-item identity or a selection route
validated by the shutdown boundary itself rather than by an action hash.

The name-based route already exists and is the narrower fix: `NativeMenuItems` matches an item by
its object name at `OBJECT_NAME_OFFSET` 0x1C when a `required_name` is supplied, which is how the
pause-menu Select and Back buttons are identified elsewhere. What is missing is the pause-menu Quit
item's name value, so the phase cannot yet select it by name. Establishing that value, or proving
the last walked item is Quit and selecting on position, removes the dependence on
`focused_item_action`, which does not discriminate items in this menu.

Note that `scratch/states/save-menu.p2s` cannot drive either phase: it loads with the pause menu
already open, so `probe_gameplay_pause_menu` cannot establish the inactive-menu state it requires. A
closed-menu gameplay state is needed; the Marine M1 mission state works.

## Remaining work

- Firmware services beyond the boot, mission-archive, game-save, game-load,
  slot-enumeration, guest-reset, and movie slices are not yet inventoried.
- Stable title completion is unobserved, and the guest-owned shutdown boundary is
  now diagnosed rather than open: see the shutdown section above. Selecting the
  Quit item by name is unblocked on the host side, because the focused item's
  guest name hash is now observed; it needs the pause-menu Quit item's name value.
- Service negative paths (unobserved result types, failing and busy services)
  are not exercised for the inventoried contracts.
- Clock, counter, and interrupt relationships in the title's own state machine
  remain unproven.
- `GsGetIMR` is statically excluded from the normal-title path by a dead
  screen-capture helper; that exclusion is not runtime-confirmed.

## Resolution

Not resolved. The current census is the first partial S025 slice; it does not
establish a BIOS-free path or any S026–S028 behavior.
