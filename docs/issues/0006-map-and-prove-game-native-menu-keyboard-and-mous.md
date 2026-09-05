---
id: 6
title: Map and prove game-native menu keyboard and mouse actions
status: investigating
symptom: pause-menu keyboard and pointer actions are native, but product-window delivery and broader menu coverage remain unverified
state_items: S010
tags: input,menu,keyboard,mouse,re
created: 2026-08-27
updated: 2026-09-05
---

## Root cause

AVP:E registers active menu callbacks dynamically, so there is no stable global
menu pointer. More importantly, synchronous `ExecuteUntil` suppresses ordinary
EE/IOP/timer events; focused activation can call `Load__5GMenu`, which needs
those events and therefore cannot return through that diagnostic boundary. The
same boundary is not valid for every pointer-motion state: on the Save Game
menu, a direct `GfsPointer::Input_UpdatePositionAbsolute` returns through the
game's `SleepThread` syscall at `0x002b3d40` rather than the interrupted
`0x002ce2c8` return PC, leaving the EE at BIOS `EENULL` (`0x00081fc0`) until
the three-million-cycle bound faults the shuttle.

## What was tried / dead ends

### Dead end (2026-08-27)
Direct synchronous GMenu::Input(action=Activate) is unsafe on the callback-owned
Press START item: it never returned to the synthetic EE-call frame and exceeded
both 3M and 30M cycle budgets, pausing/faulting the shuttle until savestate
reload. That source can replace shell/menu ownership and must be queued onto
AVP:E's normal input/update execution instead of being treated as a returning
diagnostic call. This result does not apply to the later grounded synchronous
mission-load modal.

## Current findings

Active GMenu discovery is grounded through GInputDevice's callback ZArray at
+0x48. Directional navigation, deferred activation, and virtual cancel are
verified on pause/Save menus. The active callback-owned menu pointer is
identified by its GetMenuItem, absolute-motion, and action virtual slots;
deferred MenuCheck hit-testing focused distinct Resume and Save objects, and
pointer activation entered Save. `HostInputRouter` maps arrows/WASD,
Enter/Space, Escape/Backspace, pointer motion, and primary/secondary edges to
typed menu or gameplay owners without virtual-pad writes.

The prior Press START transition is not stable evidence. A later identical
saved-state probe completed and restored its deferred activation call but left
the source menu active for 90 seconds, falsifying C012. This did not reproduce
on pause Save activation and is not caused by the shared pointer-motion
extraction; the exact title-state dependency remains under investigation.

The clean mission-load variant is now covered. Before callback registration,
`NativeMenuInput` validates the exact `GMissionGoalsMenu` singleton/vtable,
waits for the unique exact Exit object, focuses it through its title virtual,
and invokes `GMenu::Input(Activate)` synchronously. This source cannot use the
deferred path: it is requested reentrantly at the observed modal loop PC, which
can falsely satisfy the deferred return check before the queued action runs.
The verified run focused the exact object, restored the stack, cleared the
singleton, and reached the grounded `ShellLoadLevel` continuation.

The Save Game pointer failure is now grounded rather than treated as a
coordinate or selector-mode defect. The same menu had selector mode zero both
before and after entry. `SetPos`, `UpdateWorldPos`, and `StartSelection` all
returned individually, including the linked-render path and the nonzero
`StartSelection` argument used by `Input_UpdatePositionAbsolute`; only the
complete original routine reached `SleepThread`. The next correct boundary is
the normal `GInputDevice` callback dispatch that owns this yielding action, not
another direct or deferred call to `Input_UpdatePositionAbsolute`.

That dispatch is now observed at `0x001147cc` without mutation. It runs with
the game-owned `CInputData` buffer at device `+0xac`; its registers carry the
resolved owner (`a0`), current `CInputDef` (`a2`), and callback member
descriptor (`t9`). A live neutral Save Game run reached the normal menu analog
callback 114 times. The menu pointer is registered separately with virtual
descriptor `{0, 0xd8, 0}` but does not fire while the backend is neutral. The
dispatch-bound queue now selects that registered pointer definition at this
seam. `POST /input/menu-pointer-dispatch` proved it updates the Save Game
pointer through the ordinary callback. Static decompilation of that callback
shows it invokes its virtual `MenuCheck` twice itself: in
`GAvPPointer::Input_UpdatePosition` and again in the base
`GfsPointer::Input_UpdatePosition`. The former post-return third check was
therefore redundant and removed. The formerly tested `(431.33,178.80)` point
intersects a `GMiner` render rectangle, so `GetMenuItem` correctly rejects it.
The measured `GMenuButton` rectangle `(268,366)`–`(292,390)` instead focused
`0x015AFD10` at `(280,378)` through the native callback. The original
`GfsPointer::Input_Action` then completed through the deferred scheduler with
exact stack restoration. Product-host live-window delivery remains unverified.

`HostInputRouter` now uses `MovePointerThroughDispatch` for every discovered
menu rather than the synchronous absolute-motion route. The same dispatch probe
preserves the pause-menu Save focus/activation contract and the Save Game
button contract; real-window delivery remains the unproven product boundary.

### Finding (2026-09-04, resolved product-launch refusal)

The first normal `./run.sh` route rebuilt the standalone `avpe` host, loaded
the supported CHD, and opened the Vulkan GS path, but exited with status 1
because the standalone settings path had not populated `ImGuiManager`'s text
font list. `AddTextFont()` therefore returned null and GS initialization
failed. Loading the bundled Roboto resource before GS startup resolves that
cause: the normal launcher now reaches CRTC setup and multiple game FMVs. The
remaining `Keyboard/...` binding rejections are separate standalone input
configuration warnings, not the GS failure's cause. Do not claim real-window
routing until visible events reach `HostInputRouter`.

### Finding (2026-09-05, native title activation)

The live eight-callback title registry exposes two bindings on the focused
`GMenuButton`, both resolving through `{0,0xcc,0}` to `GMenuItem::HotKeyActivate`
at `0x00120F40`. It has no ActivateFocused helper or menu-owned activation
callback. The native route therefore returned HTTP 409 even though the
physical route worked. `NativeMenuItems` now owns the extracted bounded
descendant/handle lookup, preserves ActivateFocused precedence, and admits the
current focused descendant's exact registered HotKeyActivate as its fallback.
The body ignores CInputData and invokes the item's existing focus/activation
virtuals. No pad state, phase pointer, or synthetic execution frame is needed.

The live native action dispatched the focused title button exactly once,
completed ticket 1 through normal dispatch, observed the press-start and
profile-construction entries in order, and reached `GProfileMenu` vtable
`0x00343750`. The standalone `--probe-native-menu-activate` scenario from that
captured title state also passed with zero card changes and graceful shutdown.
Its before/after image hashes were identical, so this is callback/lifecycle
evidence, not visual presentation evidence.

The new discovery tests retain the unique mission-goals Exit contract, reject
unreadable or conflicting selected owners, enforce the 256-descendant bound,
coalesce same-item bindings, and refuse underlying menu activation when either
grounded `GAttractExit` callback remains registered. Unrelated expired callback
owners must remain ignorable: inspecting every owner before classification
broke the pause fixture. The exact attract function prefilter preserves that
existing registry contract without weakening selected-owner validation.

The retained `--probe-native-menu` pause scenario passed with its matching
isolated card: Down moved focus, activation selected the existing hidden
ActivateFocused owner (preserving its precedence), `GSaveGameMenu` opened, and
Cancel restored the pause menu with exact deferred-stack restoration. The card
remained byte-identical. Omitting that fixture's card reaches a different menu
without valid focus and is not equivalent save-menu regression evidence.

### Finding (2026-09-05, native attract cancellation)

The current `press-start.p2s` run initially had eight title callbacks; normal
simulation later entered the 52-callback attract state with owner `0x01765D10`.
Native Activate then refused with “no active game menu owns navigation
callbacks.” Menu discovery cannot own admission for this non-menu input owner.
`NativeAttractInput` now selects the exact registered button callback at
`0x00206A60` (not its analogue peer at `0x002069E0`); its recovered body ignores
input data and calls the existing `CShell::SetNextLevel` route. `NativeMenuInput`
composes this before requiring a menu, retaining the synchronous mission-goals
path and the separate prohibition on activating a menu beneath an attract owner.

From the captured live attract state, one native Activate completed dispatch
ticket 1 with source `attract-cancellation`. Its exact button descriptor fired
once, the valid registry changed from 52 to 8 callbacks, and `GPressStartMenu`
returned while the armed profile observer still had both entry ordinals zero.
A separate second native Activate completed ticket 2, dispatched the focused
button, and reached `GProfileMenu` with press-start/profile ordinals 1/2.
`GET /debug` reported injection masks `0000`/`0000` and neutral pad reports.
No phase/timer writes, synthetic input data, or chained title activation occur.
The run was surfaceless/null-muted; this is lifecycle and native-dispatch
evidence, not real-window event or visual verification.

Four new production-reader tests distinguish absent, available, analogue-only,
invalid, and competing attract owners; preserve unrelated expired entries;
coalesce same-owner button aliases; and select cancellation without any menu.
The matching-card `--probe-native-menu` regression also passed after this
composition change, preserving pause navigation, hidden-hotkey activation,
Save-menu entry, and Cancel with zero changed card bytes.

Remaining work: verify real-window key/mouse delivery, implement native
logo cancellation through its full lifecycle, and cover broader
in-game menu variants.
