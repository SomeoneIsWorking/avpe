---
id: C012
kind: claim
status: holds
created: 2026-08-27
tags: input,menu,deferred
depends: thirdparty/pcsx2/pcsx2/AVPE/EECallShuttle.cpp#TryCompleteDeferredCall, thirdparty/pcsx2/pcsx2/AVPE/NativeMenuInput.cpp#Apply, tools/run_control_test.py#probe_native_menu
reconfirmed: 2026-08-27
verified_at: 2026-08-27 01:25:34
---

## Claim

AVP:E menu activation and cancel complete through deferred normal-scheduler guest calls with exact stack restoration and game-owned menu transitions

## Evidence

Windowless/null-muted probes: Press START 0x01346590->0x0147D230 in 6902716 cycles; pause Save 0x012E85A0->0x015AFA70 in 11381330 cycles; virtual cancel handler 0x00124C20 restored 0x012E85A0 in 138931 cycles; every deferred completion reported stack_restored=true at a nonzero staging address and both runners shut down gracefully.

## What would falsify it

either saved-state probe no longer completes, reports failed stack restoration, or fails to change the active game-owned menu as recorded

## Re-confirmed 2026-08-27

Reverified after final deferred/menu/router changes: pause navigation+activation+virtual-cancel probe and Press START activation probe both passed surfaceless/null-muted with exact stack restoration and graceful shutdown; combined mission pointer+mouse regression also passed.
