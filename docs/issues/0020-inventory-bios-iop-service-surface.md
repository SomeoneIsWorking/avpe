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
pause-menu Select and Back buttons are identified elsewhere.

### The seven pause-menu item identities, observed

`NativeMenuItems::ReadItemName` now exposes that hash through the menu-state route as
`focus_name`, and walking the live pause menu shows the collision is entirely in the action
value, not in the items:

```text
step     object      focus_name  focus_text_address  focused_item_action
0        0x0150B370  0x6B7CD81C  0x01428134           0x95DF2577
1        0x0150BE50  0xE1235D6B  0x0142828C           0xCA788CFB
2        0x01517470  0x914383A8  0x014283D8           0xCA788CFB
3        0x01517F60  0x931F993B  0x0142850C           0xCA788CFB
4        0x01518A40  0x513B080C  0x01428644           0xCA788CFB
5        0x01519520  0xF7278F25  0x01428778           0xCA788CFB
6        0x0151A000  0xF1F58099  0x014288AC           0xCA788CFB
```

All seven name hashes are distinct, so the walk does reach seven distinct items and the guest does
identify each one.

### Correction: Quit is not in this menu, and the shared action is not noise

An initial reading of the table above was wrong in two ways, and both matter.

First, `focused_item_action` is not a defective field. The guest's name hash is
`CCRC32::GetCRC` at `0x0010C4E0`: CRC-32 reflected, polynomial `0xEDB88320`, table at `0x002D1E40`
(256/256 words match), initial value `0xFFFFFFFF`, **no final inversion**, 8-bit characters. That is
`(binascii.crc32(s)) ^ 0xFFFFFFFF`. Decoding the observed values:

```text
0x6B7CD81C Pause_Resume      0xE1235D6B Pause_Save       0x914383A8 Pause_Load
0x931F993B Pause_Bestiary    0x513B080C Pause_Option     0xF7278F25 Pause_Restart
0x95DF2577 CancelKillMe      0xCA788CFB LoadMenu         0x3CF57571 QuitGame
```

`0x6B7CD81C` and the five other `Pause_*` values are reproduced exactly by hashing those literals.
`QUIT_GAME_ACTION` is therefore **correct**: it is `GetCRC("QuitGame")`. It fails only because the
walk never visits an item carrying it.

Second, and this is the actual blocker: **the Quit item is not in the pause menu's top level.**
Step 0 carries action `CancelKillMe` (resume). Steps 1-6 all carry `LoadMenu`, which
`GBaseMenu::ItemActivated` dispatches to `Load__5GMenuF...GMenu` — they open submenus. Six siblings
share one `LoadMenu` value because `GMenuListBox::Add` instantiates them from a single
`CEmbeddedFillData` template and copies its stored name hash verbatim, so the value is *correct for
each* item and simply is not a unique identity. Quit lives inside one of those submenus.

So replacing the action match with a name match would not have fixed anything: it selects among
seven submenu openers, none of which is Quit. `GMenu::ItemActivated` at `0x00124EF0` compares
`item+0x110` against `GetCRC("QuitGame")` and calls the only `CShell::Quit` on that path, so the
selection route that works is: open a `LoadMenu` submenu, then find the item whose `+0x110` is
`0x3CF57571`.

The project already has that route. `src/avpe/native_pause_quit_probe.py` reads the guest's rendered
selection-rectangle list, moves the native pointer onto each rectangle, and identifies the item by
its **live text** read from `item+0x148` together with its action and its `item+0x114` target. It
never selects by screen coordinate. The pointer phase already uses it; that phase arms the boundary
correctly and still observes no `CShell::Quit`, so the remaining gap is which submenu to enter and
whether the confirmation needs a second activation.

The pause items' name hashes are `GetCRC("MainSelectButton")` = `0x6449F1DE` and
`GetCRC("MainBackButton")` = `0x36D11C7B`, recovered from the `CHausLabelFixup` labels in
`MASTER.TBD` (issue 0008, glyph identity).

Note that `scratch/states/save-menu.p2s` cannot drive either phase: it loads with the pause menu
already open, so `probe_gameplay_pause_menu` cannot establish the inactive-menu state it requires. A
closed-menu gameplay state is needed; the Marine M1 mission state works.

## Firmware service surface, statically enumerated

A read-only static pass over the whole `SLUS_201.47` image (164 `syscall` sites, 124 distinct
numbers) established the shape of the firmware dependency. Coverage is bounded honestly: 76.4% of
the `main` block is inside function bodies, and completeness of the remaining 23.6% was not proven.

**There is no syscall dispatch table in the executable.** Every `syscall` site is a wrapper that
loads the number into `$3` and traps; the table lives in BIOS RAM and the guest finds and patches it
at runtime. `kFindAddress` at `0x002bc988` word-scans the BIOS mirror for a marker;
`GetSystemCallTableEntry` at `0x002bc9d0` returns `FindAddress(0x2bc988) - 0x20c`. `_InitSys` at
`0x002bca40` runs from crt0 (`jal` at `0x00100084`) and drives the whole bootstrap. This is a hard
HLE prerequisite: without BIOS RAM there is no table to find, and `FindAddress` is itself a syscall.

**The guest writes code into BIOS RAM.** `InitExecPS2` at `0x002bcb50`, reached from crt0, issues
`setup` (0x74) then `Copy` (0x5A) to place `0x7A8` bytes of guest code at BIOS `0x80074000`, then
installs further shims. An HLE must reproduce that memory image and patched table, or replace
`Copy`/`setup`. This is the highest-risk item for a BIOS-free path.

**The IOP service surface cannot be derived from this ELF.** A byte scan for `\x7fELF`, `.irx`,
`_libent`, and every 8-char library name PCSX2 knows found zero embedded module images and zero
library-name strings, and `sceSifGetModuleEntry` is not linked at all. There is no by-name export
lookup: `_sceSifLoadModule` binds services by hardcoded numeric SIF RPC id. So the IOP ordinal
inventory must come from loading `cdrom0:\IOPRP242.IMG;1` plus the seven disc IRX files the IOP
bootstrap at `0x00186b70` loads — not from static analysis of this program. The IOP reset packet
is built with `count = 0` (image mode), so the module set comes from the disc.

`sceSifRegisterRpc` has zero flow references, so the guest registers no EE-side RPC handler and
there is no IOP->EE SIF-RPC back-channel to reproduce. `SIO2MAN.IRX` is loaded but never bound.
Syscalls 6 and 7 (`LoadExecPS2`, `ExecPS2`) have zero references — module loading goes through SIF
RPC, not the EE syscall path.

Of the 124 numbers, 18 have runtime observations. `0x05` and `0x08` have zero static callers, so
they are issued by the BIOS kernel itself, not the guest. 61 numbers have at least one static caller
and no observation; the largest untested groups are thread/sema core (`0x20`-`0x22`, `0x25`, `0x29`,
`0x2B`, `0x33`, `0x37`, `0x38`), interrupt and DMAC handler registration (`0x10`-`0x17`, `0x1A`-
`0x1C`, never observed at all), SIF register/DMA (`0x79`, `0x7A`, `0x76`, `0x6B`, `0x73`), and OSD
config (`0x4A`, `0x4B`, `0x6F`).

### Correction: there is no sign-magnitude decode bug

An initial reading concluded that PCSX2's sign-magnitude decode mislabels the alarm services and
that `SetAlarm` (immediate `0xfc`) decodes as non-returning `KExit` (4). **That is false, and the
instruction word itself refutes it.** `addiu` sign-extends its 16-bit immediate, so:

```text
0x240300FC  addiu v1,zero,+252  -> v1 = +252 (positive) -> call = 0xFC
0x2403FFE6  addiu v1,zero,-26   -> v1 = -26  (negative) -> call = 0x1A
0x2403FFFC  addiu v1,zero,-4    -> v1 = -4   (negative) -> call = 0x04
```

`0x240300FC` was misread as `-4`; its immediate is `0x00FC`, which is positive. Sign-magnitude
therefore yields `0xFC` for `SetAlarm`, exactly as intended, and the census's `number: 252` **is**
attributable to the guest's `SetAlarm` wrapper. The `i`-variants collapse onto their base service
only where ps2sdk's own notation is negative, which is consistent. No decode change is warranted.

### Real naming gap found alongside it

The census reports `name: "unknown"` for 252 because `R5900::bios[]` is declared `[256]` but
initialized for only `0x00`-`0x7F`; the remaining entries are null, so every service above `0x7F`
falls through to `"unknown"`. That covers the whole alarm group `0xFC`-`0xFF`, which the game
demonstrably calls. `EeSyscallName` already overrides a few entries with ps2sdk authority and
should extend that to the alarm group. Names for `0x53`-`0x5B` are also stale in `R5900::bios[]`
(`RFU08x_*EventFlag` where ps2sdk and the binary's own wrapper symbols say `PutTLBEntry`,
`_SetTLBEntry`, `GetTLBEntry`, `ProbeTLBEntry`, `ExpandScratchPad`, `Copy`, `GetEntryAddress`).

## Remaining work

- Firmware services beyond the boot, mission-archive, game-save, game-load,
  slot-enumeration, guest-reset, and movie slices are not yet observed at runtime.
  The static surface is now enumerated above; the gap is 61 statically referenced
  numbers with no observation, prioritised there.
- The IOP ordinal inventory cannot be derived from `SLUS_201.47` at all. It requires
  loading `IOPRP242.IMG` and the seven disc IRX modules the IOP bootstrap pulls.
- `InitExecPS2`'s BIOS-RAM patch at `0x80074000` and the runtime-found syscall table
  are unexercised, and both are hard prerequisites for a BIOS-free path.
- Services above `0x7F` are observed but unnamed, including the whole `0xFC`-`0xFF`
  alarm group the game calls.
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
