---
id: 13
title: Keep FSSOUND cdvdman error state native after native reads
status: resolved
symptom: FSSOUND native sceCdRead succeeds, then sceCdGetError falls through to the original optical controller and can observe stale unrelated error state
state_items: S024
tags: assets,audio,cdvd,native-io,error
created: 2026-08-28
updated: 2026-08-28
---

## Root cause

The title-specific cdvdman HLE claims FSSOUND `sceCdRead`, but import index 8 (`sceCdGetError`) remains on the original cdvdman path. FSSOUND calls it immediately after native reads, so the result is not owned by the backend that performed the read.

## Required change

Record a bounded, one-shot native completion result keyed by the calling IOP stack when a synthetic-LSN read is claimed. Consume that result only for the matching immediate `sceCdGetError`; unrelated callers remain unhandled. Reset transient completions with guest state.

## Acceptance

- Interleaved caller stacks cannot consume each other's result, and each completion is consumed at most once.
- Successful native reads return native no-error through `sceCdGetError`; unrelated calls retain the original cdvdman implementation.
- Bounded production tests exercise matching, wrong-stack, interleaved, replacement, capacity, reset, and OTHER-answer behavior.
- A surfaceless/null-muted native stream run observes recorded and consumed native completions, zero rejected records, zero active tokens, and no optical fallback for the stream.

### Resolution (2026-08-28)
Added fixed-capacity caller-stack completion tokens for claimed native cdvdman reads, consumed them only by the matching sceCdGetError import, and verified 2 recorded/2 consumed with zero rejects or active tokens in a clean surfaceless/null-muted MENU01 stream run.
