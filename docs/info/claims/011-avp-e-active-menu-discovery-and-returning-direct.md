---
id: C011
kind: claim
status: holds
created: 2026-08-27
tags: input,menu,keyboard,verification
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeMenuInput.cpp#Apply, tools/run_control_test.py#probe_native_menu
reconfirmed: 2026-08-27
verified_at: 2026-08-27 02:53:26
---

## Claim

AVP:E active-menu discovery and returning directional input change game-owned pause-menu focus without virtual-pad writes

## Evidence

The surfaceless/null-muted menu probe resolved unique active GMenu 0x012E85A0 from 32 GInputDevice callbacks, then GMenu::Input(Down) changed focus handle/object from 0x03400000/0x015DFB60 (Resume) to 0x03410000/0x015E0640 (Save) in 7,953 EE cycles. Before/down snapshots differed and the process shut down gracefully with exit zero. Synchronous Activate is explicitly rejected because separate negative work proved it can replace menu/shell ownership without returning.

## What would falsify it

The active callback registry resolves zero or multiple menu owners in the verified pause state; a returning directional action no longer changes game-owned focus; the bridge writes virtual-pad state; unsupported activation is accepted; or the probe cannot shut down gracefully.

## Re-confirmed 2026-08-27

2026-08-27 final surfaceless/null pause-menu run: native Down changed focus from Resume 0x015dfb60 to Save 0x015e0640; read-only menu-state snapshots observed the game-owned transition and the run shut down cleanly.

## Re-confirmed 2026-08-27

Reverified after extending NativeMenuInput with pointer actions: the surfaceless/null-muted pause probe changed focus from Resume 0x015DFB60 to Save 0x015E0640 through returning directional calls, then completed activation and virtual cancel with exact stack restoration and graceful shutdown.
