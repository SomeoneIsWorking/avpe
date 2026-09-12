---
id: C040
kind: claim
status: falsified
created: 2026-09-04
tags: bios,load,memory-card,inventory
depends: src/avpe/native_game_load_probe.py#run_game_load_phase, thirdparty/pcsx2/pcsx2/AVPE/NativeGameLoadBoundary.cpp#ObserveEeExecution, thirdparty/pcsx2/pcsx2/AVPE/NativeBiosEventStore.cpp#RecordIopOracleImportReturn
---

## Claim

AVP:E's normal Pause to Load to populated-slot route accepts the produced slot-0 record, crosses all three GLoadPacifyMenu calls and the exact CProfile LoadGame entry/return with result zero, completes the synchronous mission-goals modal, and yields a bounded schema-v6 BIOS/IOP slice without mutating the source card

## Evidence

scratch/control-test/game-load-bios.json; scratch/control-test/game-load-bios-inventory.json; successful 2026-09-04 surfaceless/null-muted game-load phase; focused native and Python probe tests. A 2026-09-12 repeat with the same `mission1.p2s` and `after-slot0.ps2` inputs failed to settle the loaded menu: the guest focus object remained zero and the control route timed out. The emulator log reports a Europe BIOS in the savestate and the runner's USA BIOS, so the previously observed success is historical evidence only until that pairing is deterministic.

## What would falsify it

the same matching state/card route fails to reach the exact CProfile entry/return, returns nonzero, cannot complete the exact mission-goals Exit action, mutates the source card, or reports sequence/overflow errors
