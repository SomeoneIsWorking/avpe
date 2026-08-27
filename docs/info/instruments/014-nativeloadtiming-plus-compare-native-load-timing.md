---
id: I014
kind: instrument
status: trusted
created: 2026-08-28
---

## Instrument

NativeLoadTiming plus compare_native_load_timing.py startup timing differential

## Validated by

Production emitted three clean oracle and three clean native samples with identical 1-to-3 boundary ordinals and zero EE/IOP/frame spread. A copied native sample with a changed end ordinal was rejected for boundary_ordinal_drift, and copied samples with native EE timing raised to oracle timing were rejected for no_measured_reduction. Policy also rejects wrong backends, byte tracing, malformed endpoints, recomputation disagreement, excessive spread, and fewer than three pairs.

## Known failure modes

The instrument covers only the grounded startup interval, not mission loading,
and host elapsed is secondary because it includes host scheduling noise. It
does not prove cache bounds, cold/warm cache state, or failure equivalence.

The first six-run orchestration attempt falsely rejected a valid comparison
because it hashed PCSX2's entire INI; the `-nogui` Qt frontend still rewrites
window geometry/state and game-list header bytes. The corrected identity keeps
every persisted setting except those diagnosed UI-layout fields, and its
regression changes an emulation setting to prove that semantic drift remains
visible.
