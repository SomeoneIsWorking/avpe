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

The product host has no typed menu-input owner. AVP:E registers active menu
callbacks dynamically, so there is no stable global menu pointer to call, and
focused-item activation can replace menu/shell ownership without returning to
the synchronous EE-call boundary.

## What was tried / dead ends

### Dead end (2026-08-27)
Direct synchronous GMenu::Input(action=Activate) is unsafe: on the Press START item it never returned to the synthetic EE-call frame and exceeded both 3M and 30M cycle budgets, pausing/faulting the shuttle until savestate reload. Activation can replace shell/menu ownership and must be queued onto AVP:E's normal input/update execution instead of being treated as a returning diagnostic call.

## Current findings

Active GMenu discovery is grounded through GInputDevice's callback ZArray at
+0x48: matching GMenu callback function pointers resolve a unique owner handle
through TheHandleArray. On the pause menu, typed Down changed the game-owned
focused item from `0x03400000` to `0x03410000` without virtual-pad writes.
Directional input is the verified subset; activation, cancel, mouse
hit-testing, broader menu coverage, and product host routing remain open.
