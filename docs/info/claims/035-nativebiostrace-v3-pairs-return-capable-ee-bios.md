---
id: C035
kind: claim
status: holds
created: 2026-08-30
tags: bios,inventory,mission,syscall
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeBiosTrace.cpp#ObserveEeSyscallReturn, thirdparty/pcsx2/pcsx2/AVPE/NativeBiosEventStore.cpp#RecordEeBiosSyscallReturn, src/avpe/native_bios_probe.py#bios_trace_is_verified, src/avpe/bios_inventory.py#_summarize_ee_syscalls
reconfirmed: 2026-08-31
verified_at: 2026-08-31 16:22:21+03:00
---

## Claim

NativeBiosTrace v5 pairs return-capable EE BIOS syscalls at the instruction after their syscall and distinguishes captured 32-bit results, captured declared 64-bit results, void returns, unobserved unknown result types, and non-returning control transfers. Two completed clean mission captures repeat the same 11 syscall identity/disposition surface with zero pairing errors; native and Python discriminators prove the full-width `GsGetIMR` representation, though no AVP:E phase has exercised that GS path live.

## Evidence

scratch/control-test/bios-mission-service-v3-d.json; scratch/control-test/bios-mission-service-v3-e.json; scratch/control-test/bios-mission-service-v3-de-inventory.json; NativeBiosTraceTest and Python validator/inventory tests

## What would falsify it

a same-input completed mission capture has a return-capable BIOS entry without its exact stack/resume-PC return, reports a result for a void or non-returning syscall, omits a supported scalar result, misencodes a declared 64-bit result, changes one of the 11 syscall identity/disposition classes, or the observer changes guest execution

## Re-confirmed 2026-08-30

PCSX2 fork commit e233445; scratch/control-test/bios-mission-service-v3-d.json; scratch/control-test/bios-mission-service-v3-e.json; scratch/control-test/bios-mission-service-v3-de-inventory.json; 27 focused native BIOS-trace tests; 74 focused Python control/inventory tests; Clang product build
