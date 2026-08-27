---
id: 12
title: Bound native asset caching and prove loading behavior
status: investigating
symptom: Native asset reads are synchronous and startup/transition loading reduction has not been measured against the optical behavior
state_items: S024
tags: assets,cache,loading,timing
created: 2026-08-27
updated: 2026-08-27
---

## Scope

Add a bounded cache/prefetch layer behind NativeAssets without changing guest-visible read, seek, short-read, zero-tail, or failure behavior. Measure symmetric startup and representative transition boundaries with byte tracing disabled.

## Acceptance

- Cache memory and file lifetime are explicitly bounded and reset safely.
- Native and oracle success plus missing/corrupt/error results remain behaviorally equivalent; failures never silently fall back.
- At least three alternating clean pairs record EE cycles, IOP cycles, guest frames, and secondary host elapsed time across the grounded TBF-open to post-MENU01-search seek interval.
- Raw samples, determinism spread, and reduction are recorded without averaging away boundary drift.
- Runs remain surfaceless, null-muted, isolated, and card-hash preserving.
