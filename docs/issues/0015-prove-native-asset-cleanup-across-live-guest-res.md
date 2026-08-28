---
id: 15
title: Prove native asset cleanup across live guest reset
status: open
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
