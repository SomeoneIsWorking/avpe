---
id: C034
kind: claim
status: falsified
created: 2026-08-30
tags: bios,iop,inventory,mission
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeBiosTrace.cpp#RecordImport, thirdparty/pcsx2/pcsx2/IopBios.cpp#CompleteImportTrace, thirdparty/pcsx2/pcsx2/R5900OpcodeImpl.cpp#SYSCALL, src/avpe/native_bios_probe.py#bios_trace_is_verified
reconfirmed: 2026-08-30
verified_at: 2026-08-30 04:29:37+00:00
falsified_on: 2026-08-30
---

## Claim

NativeBiosTrace v2 distinguishes BIOS and oracle fallthrough from direct and handled-HLE outcomes without serializing stale return registers; across three completed clean mission captures the same 11 EE syscall and 4 IOP import service identities recur, all import summaries match exactly, and only the sceSifSetDma BIOS call total differs by one.

## Evidence

scratch/control-test/bios-mission-service-v2-a.json; scratch/control-test/bios-mission-service-v2-b.json; scratch/control-test/bios-mission-service-v2-c.json; scratch/control-test/bios-mission-service-v2-repeat.json; focused NativeBiosTrace and Python inventory tests

## What would falsify it

a v2 capture contains a result when result_valid is false, omits a result when result_valid is true, changes one of the clean-mission service identities under the same inputs, or routes a handled HLE/fallback outcome differently from guest execution

## Re-confirmed 2026-08-30

scratch/control-test/bios-mission-service-v2-a.json; scratch/control-test/bios-mission-service-v2-b.json; scratch/control-test/bios-mission-service-v2-c.json; scratch/control-test/bios-mission-service-v2-repeat.json; focused NativeBiosTrace and Python inventory tests

## FALSIFIED 2026-08-30

Static direct-path audit found that GetOsdConfigParam2 returns directly without assigning v0 while v2 marks every direct outcome result_valid=true; the ix86 constant FlushCache/iFlushCache optimization also bypasses the shared observer. The three mission artifacts contain no direct outcomes and remain valid for their observed surface, but the generalized v2 direct-result and engine-coverage claim is false.

> Anything that cited this claim as proof must be re-checked. Grep the repo for it.
