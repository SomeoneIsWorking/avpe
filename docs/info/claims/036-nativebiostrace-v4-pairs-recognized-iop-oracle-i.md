---
id: C036
kind: claim
status: holds
created: 2026-08-31
tags:
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeBiosTrace.cpp#RecordIopOracleImportEntry, thirdparty/pcsx2/pcsx2/AVPE/NativeIopReturnSites.cpp#Register, src/avpe/native_bios_probe.py#bios_trace_is_verified
---

## Claim

NativeBiosTrace v4 pairs recognized IOP oracle imports by exact stack and caller return PC and records the eventual signed v0; two clean mission captures paired all 527 cdvdman.sceCdGetError calls at result 0 with zero pending or overflow and repeated service identity sets

## Evidence

scratch/control-test/bios-mission-service-v4.prev.json; scratch/control-test/bios-mission-service-v4.json; NativeBiosTraceTest.*; tests.test_control_test; tests.test_bios_inventory

## What would falsify it

a clean mission capture has unmatched or overflowed IOP pairing, a mismatched service/boundary identity, or sceCdGetError returns a different result under the same guest inputs without an explained semantic cause
