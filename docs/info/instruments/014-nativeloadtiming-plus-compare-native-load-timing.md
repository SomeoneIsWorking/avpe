---
id: I014
kind: instrument
status: trusted
created: 2026-08-28
---

## Instrument

NativeLoadTiming and NativeMissionLoadTiming plus
compare_native_load_timing.py timing differential

## Validated by

Production emitted three clean oracle and three clean native samples with identical 1-to-3 boundary ordinals and zero EE/IOP/frame spread. A copied native sample with a changed end ordinal was rejected for boundary_ordinal_drift, and copied samples with native EE timing raised to oracle timing were rejected for no_measured_reduction. Policy also rejects wrong backends, byte tracing, malformed endpoints, recomputation disagreement, excessive spread, and fewer than three pairs.

Mission schema v2 separately emitted three alternating clean oracle/native
samples across the grounded ShellLoadLevel entry and continuation. Every oracle
sample positively exercised the instrument with 1,985 sector deliveries and
positive read/sector-ready waits; every native sample reported zero waits and
deliveries. Policy regressions force rejection when copied native activity is
made nonzero, copied oracle activity is zeroed, or a wait count/cycle pair is
made inconsistent. The live native envelope also rejects dropped path
observations and any original fallback increase for an observed TBD, movie, or
stream path.

## Known failure modes

Host elapsed is secondary because it includes host scheduling noise. Optical
activity covers scheduled waits and sector deliveries at the CDVD owner; the
native-open snapshot separately covers original-fallback counts. The instrument
does not prove cache bounds, cold/warm cache state, or malformed-disc failure
equivalence.

The first six-run orchestration attempt falsely rejected a valid comparison
because it hashed PCSX2's entire INI; the `-nogui` Qt frontend still rewrites
window geometry/state and game-list header bytes. The corrected identity keeps
every persisted setting except those diagnosed UI-layout fields, and its
regression changes an emulation setting to prove that semantic drift remains
visible.
