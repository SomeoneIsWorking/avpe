---
id: 15
title: Prove native asset cleanup across live guest reset
status: resolved
symptom: Save-state recovery is verified, but a real in-process guest reset with an active native descriptor or synthetic CDVD mapping has not been observed
state_items: S024
tags: assets,reset,lifecycle
created: 2026-08-28
updated: 2026-08-28
---

## Scope

Add a stable control-test reset boundary and prove active native guest I/O
state is cleared in the correct order while the admitted store and bounded
cache remain valid. This is lifecycle hardening, not a gate for G005
disc-operation collapse.

## Acceptance

- A real guest reset epoch is observed without restarting the process.
- Active native descriptors, mappings, and completion tokens are empty at the
  reset boundary.
- Store admission and bounded cache remain valid; transient handles are zero.
- Native reads resume after reset with zero optical fallback for supported
  assets.

## Resolution (2026-08-28)

The control server now exposes a CPU-thread `/guest/reset` boundary owned by
`NativeGuestReset`. The production `psxReset()` path records a monotonic guest
reset epoch, and the atomic native snapshot reports that epoch alongside
descriptors, synthetic mappings, and completion occupancy.

Two clean surfaceless/null-muted runs proved the live boundary. The ioman leg
reset epoch 1→2 with TBF and INTRO.PSS descriptors active, observed empty
descriptors and mappings plus zero transient cache handles at reset, then
reopened and read INTRO.PSS natively without optical fallback. The CDVD leg
reset with MENU01.ZIV mapped at LSN 3758096384 and a live TBF descriptor,
observed all descriptors, mappings, and completion tokens empty, retained the
exact 512-page/32 MiB cache bound, then resumed native MENU01 sector reads and
matching completion consumption without fallback. Both runs reported
Running/surfaceless/null-muted status and unchanged isolated card hashes.

### Resolution (2026-08-28)
Implemented the CPU-thread /guest/reset boundary, production guest-reset epoch, and strict post-reset probe. Clean ioman and CDVD runs observed epoch 1->2, empty descriptors/mappings/completion tokens at the reset boundary, retained bounded cache and zero transient handles, resumed native reads with zero optical fallback, and unchanged isolated card hashes.
