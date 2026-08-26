---
id: 6
title: Map and prove game-native menu keyboard and mouse actions
status: investigating
symptom: pause-menu keyboard and pointer actions are native, but product-window delivery and broader menu coverage remain unverified
state_items: S010
tags: input,menu,keyboard,mouse,re
created: 2026-08-27
updated: 2026-08-27
---

## Root cause

AVP:E registers active menu callbacks dynamically, so there is no stable global
menu pointer. More importantly, synchronous `ExecuteUntil` suppresses ordinary
EE/IOP/timer events; focused activation can call `Load__5GMenu`, which needs
those events and therefore cannot return through that diagnostic boundary.

## What was tried / dead ends

### Dead end (2026-08-27)
Direct synchronous GMenu::Input(action=Activate) is unsafe: on the Press START item it never returned to the synthetic EE-call frame and exceeded both 3M and 30M cycle budgets, pausing/faulting the shuttle until savestate reload. Activation can replace shell/menu ownership and must be queued onto AVP:E's normal input/update execution instead of being treated as a returning diagnostic call.

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

Remaining work: verify the real windowed key/mouse path in a user-visible run,
determine the Press START state dependency, and cover title, mission, and
in-game menu variants.
