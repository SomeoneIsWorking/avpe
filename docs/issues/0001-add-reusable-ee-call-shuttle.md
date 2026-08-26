---
id: 1
title: Add reusable EE-call shuttle
status: investigating
symptom: control channel can read and write EE memory but cannot invoke Input_UpdatePositionAbsolute; direct screen-position writes do not move the rendered cursor
state_items: S007,S008
tags: input,pcsx2,ee-call
created: 2026-08-26
updated: 2026-08-26
---

## Root cause

The HTTP control channel owns memory and CPU-thread operations but exposes no
guest-function execution primitive. `GMarinePointer` renders from world-derived
state; writing its screen-position floats changes non-authoritative fields and
therefore cannot substitute for executing the game's
`Input_UpdatePositionAbsolute` path on the EE VM thread.

## Required change

Add a dedicated fork-local `EECallShuttle` module under `pcsx2/AVPE/`. It must
queue onto the VM thread, preserve guest state, set argument registers and PC,
return through a bounded sentinel, surface faults/timeouts, and return results
through a narrow interface. The HTTP route may submit calls but must not own the
execution machinery.

## Verification

- Invoke `CRenderer::GetResolution` on a real boot and observe plausible bounds.
- Demonstrate a failure case that the shuttle reports rather than hanging or
  returning a uniform success value.
- Use the same shipping path to invoke `Input_UpdatePositionAbsolute`; distinct
  injected coordinates must produce distinct rendered cursor positions.

## What was tried / dead ends

- Direct writes to the pointer's screen-position fields and mirrors do not move
  the rendered sprite; claim C006 records the A/B evidence.
- Raw pad injection reaches game memory but is a diagnostic/bootstrap path, not
  a native absolute-pointer implementation.
