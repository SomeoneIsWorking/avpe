---
id: 12
title: Bound native asset caching and prove loading behavior
status: investigating
symptom: Native asset reads remain synchronous and cache bounds, failure equivalence, cold/warm behavior, and representative transition timing are unproven
state_items: S024
tags: assets,cache,loading,timing
created: 2026-08-27
updated: 2026-08-28
---

## Scope

Add a bounded cache/prefetch layer behind NativeAssets without changing guest-visible read, seek, short-read, zero-tail, or failure behavior. Measure symmetric startup and representative transition boundaries with byte tracing disabled.

## Acceptance

- Cache memory and file lifetime are explicitly bounded and reset safely.
- Native and oracle success plus missing/corrupt/error results remain behaviorally equivalent; failures never silently fall back.
- At least three alternating clean pairs record EE cycles, IOP cycles, guest frames, and secondary host elapsed time across the grounded TBF-open to post-MENU01-search seek interval.
- Raw samples, determinism spread, and reduction are recorded without averaging away boundary drift.
- Runs remain surfaceless, null-muted, isolated, and card-hash preserving.

## Timing evidence

On project `edbfda4` and PCSX2 fork `87608f3`, the dedicated timing tool ran
`1:oracle, 1:native, 2:oracle, 2:native, 3:oracle, 3:native` against
SLUS-20147 CRC `64DA78A3`. Every sample used the first `TBD/TBF.TBF` open as
ordinal 1 and the seek immediately after `STREAMS/MENU01.ZIV` search as ordinal
3. Actual TBF and MENU01-seek backends matched each declared mode.

| Pair | Mode | EE cycles | IOP cycles | Frames | Host elapsed ns |
|---:|---|---:|---:|---:|---:|
| 1 | oracle | 40,408,849,912 | 5,051,106,429 | 8,213 | 137,020,651,024 |
| 1 | native | 35,312,223,239 | 4,414,027,549 | 7,178 | 120,172,455,308 |
| 2 | oracle | 40,408,849,912 | 5,051,106,429 | 8,213 | 137,021,072,161 |
| 2 | native | 35,312,223,239 | 4,414,027,549 | 7,178 | 119,761,269,569 |
| 3 | oracle | 40,408,849,912 | 5,051,106,429 | 8,213 | 138,365,053,654 |
| 3 | native | 35,312,223,239 | 4,414,027,549 | 7,178 | 121,386,093,070 |

| Metric | Oracle median | Native median | Oracle spread | Native spread | Reduction |
|---|---:|---:|---:|---:|---:|
| EE cycles | 40,408,849,912 | 35,312,223,239 | 0 | 0 | 5,096,626,673 (12.6126%) |
| IOP cycles | 5,051,106,429 | 4,414,027,549 | 0 | 0 | 637,078,880 (12.6127%) |
| Frames | 8,213 | 7,178 | 0 | 0 | 1,035 (12.6020%) |
| Host elapsed ns | 137,021,072,161 | 120,172,455,308 | 1,344,402,630 | 1,624,823,501 | 16,848,616,853 (12.2964%) |

The binary SHA-256 was
`247b17e230dab7d664ff37e1a9a984905d2d40d57a678bcb7dab66f9761e09d8`;
the source CHD SHA-256 was
`b9165e126aeb7154d95f17d2dea21c21d7754f2480e3fae5217dcdf55155e9a0`.
All samples had the same emulation-relevant configuration, byte tracing was
disabled, status was surfaceless/null-muted, and the isolated card source and
working copy stayed at
`55237edfb8bd977e22ecf84ae2d1a942f8167fd3cbf9798376259342120f2b2b`.
Copied ordinal-drift and no-reduction controls were both rejected. Detailed
ignored evidence is
`scratch/control-test/load-timing/asset-load-timing-comparison.json`.

## Remaining

- Bound cache memory and host-file lifetime and prove reset behavior.
- Prove native/oracle missing, corrupt, short-read, and error equivalence with
  no silent fallback.
- Define and exercise explicit cold and warm cache-state protocols.
- Ground and measure a representative mission/level transition; the proven
  startup interval does not stand in for that transition.
