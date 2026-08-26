---
id: 6
title: Map and prove game-native menu keyboard and mouse actions
status: investigating
symptom: mission mouse actions are verified but title, pause, mission, and in-game menus still require diagnostic virtual-pad input
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
verified on pause/Save menus; deferred activation is independently verified on
Press START. `HostInputRouter` maps arrows/WASD, Enter/Space, and
Escape/Backspace to these typed owners without virtual-pad writes.

Remaining work: verify the real windowed key-event path in a user-visible run,
map menu mouse hover/hit-testing and click activation, and cover title, mission,
and in-game menu variants.
