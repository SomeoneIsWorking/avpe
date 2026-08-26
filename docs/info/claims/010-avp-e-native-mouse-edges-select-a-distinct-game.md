---
id: C010
kind: claim
status: holds
created: 2026-08-27
tags: input,mouse,selection,command
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeInput.cpp#ApplyButtonEdge, tools/run_control_test.py#probe_native_mouse
---

## Claim

AVP:E native mouse edges select a distinct game object and dispatch the game's move command through original handlers

## Evidence

The isolated combined probe invoked handlers 0x001B52C0/0x001B52D0 and changed selected object 0x01993540 to 0x01975240. It then invoked 0x001B5300/0x001B5310 and observed current command ID change from zero to AVP:E move message 0x00060039 on the same selected object. Duplicate/unmatched edges, an unknown button name, an invalid live pointer, and release after state load returned expected 400/409 results; graceful surfaceless/null-muted shutdown exited zero. Per-run evidence is scratch/control-test/mouse-proof.json.

## What would falsify it

A supported mission click fails to change selection through the original primary handlers; right release does not record move message 0x60039 on the selected object; invalid edge state is accepted; savestate load retains held state; or repeated calls corrupt guest execution or prevent graceful shutdown.
