---
id: C008
kind: claim
status: holds
created: 2026-08-26
tags: input,re,pcsx2
depends: deps.toml
---

## Claim

The AVPE EE-call shuttle executes supported target functions on the VM thread,
stops at the interrupted return PC under a cycle budget, restores architectural
context, and fail-closes after a timeout until a known state is loaded.

## Evidence

Through the C007 runner, `CRenderer::GetResolution` at `0x00137b30` returned
`v0=0x003c9fe0` after 19 cycles and the pointed words were `0, 0, 640, 448`.
Function `0x4` returned HTTP 400, a one-cycle budget returned 504, the next call
returned 409, loading `mission1.p2s` succeeded, and the same resolution call
then succeeded again in 19 cycles.

## What would falsify it

A supported call hangs, returns without reaching the interrupted PC, corrupts
saved EE/FPU/VU0 state, advances timing inconsistently, accepts the wrong game,
allows calls after timeout without state reload, or produces a result that does
not match a direct observation of the called function's data.
