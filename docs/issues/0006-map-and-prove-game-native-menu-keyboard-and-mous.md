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
pointer through the ordinary callback. Its callback-return hook at `0x001147d8`
then queues the validated `MenuCheck` through the scheduler and restores the
interrupted callback continuation exactly. A focused run moved `GPosRot::GetPos`
from `(447.30,178.80)` to `(431.33,178.80)` and completed the follow-up safely.
That menu's hit test cleared its prior focus instead of selecting an item, so
activation remains ungrounded; the route is diagnostic and the product host
retains the verified direct pause-menu path.

Remaining work: verify the real windowed key/mouse path in a user-visible run,
determine why Save Game hit-testing clears focus, ground activation after the
dispatch-bound pointer callback, then integrate that route into the product
host and cover title and broader in-game menu variants.
