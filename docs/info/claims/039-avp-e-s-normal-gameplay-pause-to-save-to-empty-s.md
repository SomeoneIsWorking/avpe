---
id: C039
kind: claim
status: holds
created: 2026-09-04
tags: bios,save,memory-card,inventory
depends: src/avpe/native_bios_probe.py#run_bios_phase, src/avpe/memory_card_probe.py#await_memory_card_ready, thirdparty/pcsx2/pcsx2/AVPE/NativeGameSaveBoundary.cpp#ObserveEeExecution, thirdparty/pcsx2/pcsx2/AVPE/NativeBiosEventStore.cpp#RecordIopOracleImportReturn
---

## Claim

AVP:E's normal gameplay Pause to Save to empty-slot route reaches CProfile::SaveGame after three GSavePacifyMenu process calls, returns zero, mutates only the isolated working card, and yields an exactly paired bounded schema-v6 BIOS/IOP service slice

## Evidence

scratch/control-test/game-save-bios.json; scratch/control-test/game-save-bios-inventory.json; successful 2026-09-04 surfaceless/null-muted control run; NativeBiosTraceTest and Python control, card, input, and inventory tests

## What would falsify it

the same state/card route fails to reach the exact CProfile entry/return, returns nonzero, mutates the source card, leaves the card busy, or reports pending/pairing/overflow errors
