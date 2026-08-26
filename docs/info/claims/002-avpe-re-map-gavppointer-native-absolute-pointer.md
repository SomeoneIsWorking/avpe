---
id: C002
kind: claim
status: holds
created: 2026-08-26
tags: re
---

## Claim

AVPE RE map: GAvPPointer native absolute-pointer mode exists; mouse handlers ignore CInputData*; injection via UpdatePositionAbsolute + PressMouse1/ReleaseMouse1/ReleaseMouse2 with pThe__11GAvPPointer@00367720

## Evidence

docs/re/input-path.md; decomp files under scratch/re/decomp (r5900 Ghidra)

## What would falsify it

dynamic verify: if SetInputType(1) mode or handler calls fail to move cursor/command units on a live boot, this map is wrong
