---
id: C024
kind: claim
status: holds
created: 2026-08-28
tags: assets,native-io,timing
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeLoadTiming.cpp#NoteTbfOpen, thirdparty/pcsx2/pcsx2/AVPE/NativeLoadTiming.cpp#NoteCdvdSeek, src/avpe/load_timing.py#compare_load_timing_samples, tools/compare_native_load_timing.py#main
reconfirmed: 2026-08-28
verified_at: 2026-08-28 00:24:23
---

## Claim

Across three alternating clean pairs, AVP:E native storage reduces the grounded TBF-open to post-MENU01-search seek startup interval versus optical I/O

## Evidence

On project edbfda4 and PCSX2 fork 87608f3, SLUS-20147 CRC 64DA78A3 produced zero EE/IOP/frame spread. Medians fell from 40,408,849,912 to 35,312,223,239 EE cycles (12.6126%), 5,051,106,429 to 4,414,027,549 IOP cycles (12.6127%), 8,213 to 7,178 frames (12.6020%), and 137.021072161s to 120.172455308s host elapsed (12.2964%). All runs were surfaceless/null-muted, byte tracing disabled, actual backends matched modes, semantic config and binary identities matched, and isolated card hashes were unchanged. Ignored detail: scratch/control-test/load-timing/asset-load-timing-comparison.json.

## What would falsify it

the same supported-disc symmetric protocol loses a positive reduction, boundary ordinals or recomputed counters drift, actual backends do not match their modes, byte tracing is active, or binary/config/disc/card identities differ

## Re-confirmed 2026-08-28

Fresh three-pair oracle/native run after project edbfda4 produced the recorded zero-spread guest samples and 12.60-12.61% guest reductions; host median fell 12.2964%. Both copied-input controls rejected, and binary/config/disc/card/environment invariants all passed.
