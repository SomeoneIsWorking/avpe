---
id: C035
kind: claim
status: holds
created: 2026-08-30
tags: bios,inventory,mission,syscall
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeBiosTrace.cpp#ObserveEeSyscallReturn, thirdparty/pcsx2/pcsx2/AVPE/NativeBiosEventStore.cpp#RecordEeBiosSyscallReturn, src/avpe/native_bios_probe.py#bios_trace_is_verified, src/avpe/bios_inventory.py#_summarize_ee_syscalls
reconfirmed: 2026-08-30
verified_at: 2026-08-30 06:10:07+00:00
---

## Claim

NativeBiosTrace v3 pairs return-capable EE BIOS syscalls at the instruction after their syscall and distinguishes captured 32-bit results, void returns, unobserved result types, and non-returning control transfers; two completed clean mission captures repeat the same 11 syscall identity/disposition surface with zero pairing errors.

## Evidence

scratch/control-test/bios-mission-service-v3-d.json; scratch/control-test/bios-mission-service-v3-e.json; scratch/control-test/bios-mission-service-v3-de-inventory.json; NativeBiosTraceTest and Python validator/inventory tests

## What would falsify it

a same-input completed mission capture has a return-capable BIOS entry without its exact stack/resume-PC return, reports a result for a void or non-returning syscall, omits a supported 32-bit result, changes one of the 11 syscall identity/disposition classes, or the observer changes guest execution

## Re-confirmed 2026-08-30

PCSX2 fork commit e233445; scratch/control-test/bios-mission-service-v3-d.json; scratch/control-test/bios-mission-service-v3-e.json; scratch/control-test/bios-mission-service-v3-de-inventory.json; full tools/verify.py gate
