---
id: C038
kind: claim
status: holds
created: 2026-09-04
tags:
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeMissionLoadTiming.cpp#NoteOpticalWait, thirdparty/pcsx2/pcsx2/CDVD/CDVD.cpp#cdvdReadSector, src/avpe/load_timing.py#compare_mission_load_timing_samples, src/avpe/native_mission_probe.py#validate_marine_m1_evidence, tools/compare_native_load_timing.py#main
---

## Claim

AVP:E's representative native M1 ShellLoadLevel interval performs no emulated optical waits or sector deliveries and is about 74% faster than the optical oracle while preserving supported-path and card invariants

## Evidence

On project f9cab93 and fork c0e8b29, three alternating clean oracle/native schema-v2 pairs passed. Each oracle leg delivered 1,985 sectors and scheduled positive read/sector-ready waits; every native leg recorded zero action/read/sector-ready waits and zero deliveries, zero dropped paths, and no supported-path original-fallback increase. Median EE/IOP/frame/host reductions were 74.36%, 74.36%, 74.39%, and 74.55%; all envelopes and card checks passed, and both negative controls rejected their mutations.

## What would falsify it

Any change to the mission timing boundary, CDVD wait/delivery observation, native supported-path admission/fallback policy, comparison validator, runtime configuration, supported disc identity, or a repeat that observes native optical activity, path fallback, card mutation, or no material reduction
