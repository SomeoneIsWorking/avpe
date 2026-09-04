---
id: 6
title: Map and prove game-native menu keyboard and mouse actions
status: investigating
symptom: pause-menu keyboard and pointer actions are native, but product-window delivery and broader menu coverage remain unverified
state_items: S010
tags: input,menu,keyboard,mouse,re
created: 2026-08-27
updated: 2026-08-31
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

### Finding (2026-09-04, product-window launch refusal)

The normal `./run.sh` route rebuilt the standalone `avpe` host, loaded the
supported CHD, and opened the Vulkan GS path, but exited with status 1 before a
visible window appeared. The product log reports `Failed to initialize
ImGuiManager`, then `GS failed to open`; it also rejects every configured
`Keyboard/...` binding before and after the GS attempt. Consequently this is a
product-launch/resource or standalone-host initialization defect, not a failed
keyboard/mouse interaction. Do not claim real-window routing until the host
opens successfully and visible events reach `HostInputRouter`.

Remaining work: verify the real windowed key/mouse path in a user-visible run,
then cover title and broader in-game menu variants.
