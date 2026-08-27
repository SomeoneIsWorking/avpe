---
id: 12
title: Bound native asset caching and prove loading behavior
status: investigating
symptom: Native asset caching is bounded, but failure equivalence, live reset/save-state recovery, cold/warm behavior, and representative transition timing are unproven
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

- Prove native/oracle missing, short-read, and injected-error return/buffer
  equivalence with no silent fallback.
- Define and exercise explicit cold and warm cache-state protocols.
- Exercise guest reset and save/load while native descriptors and synthetic
  CDVD mappings are live; compile-time integration is not runtime recovery
  evidence.
- Ground and measure a representative mission/level transition; the proven
  startup interval does not stand in for that transition.

## Bounded cache and lifecycle

The ioman and synthetic-CDVD delivery paths now share `NativeAssetCache`, an
immutable 64 KiB page cache with an exact 512-page/32 MiB true-LRU bound. A
miss coalesces at most 16 adjacent pages through one transient host handle.
Failed or partial fills install no page; logical EOF, short reads, and I/O
errors remain distinct. `NativeAssetFile` retains only a guest cursor and an
admitted generation-safe record, so an open guest file retains no host handle.

Thirteen production tests cover valid and invalid store admission plus
unaligned/multipage cache bytes, reuse, short-read/EOF behavior, failed-fill
retry, exact-capacity eviction, true LRU, explicit page drop, and generation
change. The surfaceless/null-muted `--probe-native-asset-cache` run observed
four misses/fills, 54 hits, four resident pages (262,144 bytes), zero
evictions, one peak transient handle, and zero live handles after 53 native
TBF reads. It retained the established zero-fallthrough native TBF and optical
bootstrap boundary. The proof policy lives in
`src/avpe/native_asset_cache_probe.py`, outside the already-large runner.

Guest reset closes ioman descriptors before clearing synthetic mappings while
keeping the admitted store. Shutdown and actual disc-epoch changes close
native descriptors before cache/store unbind. Save-state format version 1
records exact native descriptor slots, cursor, admitted identity, and synthetic
LSN mappings, and restore fails closed if those identities cannot be admitted.
This path builds and passes the scoped linter. A pre-change version-0 pause-menu
state loaded successfully after the version plumbing fix. A new version-1
clean-boot state then saved and reloaded into the same running
surfaceless/null-muted target. A live state round-trip with a native descriptor
or mapping remains required.

Evidence: claim C026, instrument I016, and ignored artifact
`scratch/control-test/native-asset-cache-proof.json`.

## Store-admission invariant

Fork `fd1978a` replaces the previous “sibling manifest exists” check with a
dedicated `NativeAssetStore` index. The launcher passes the SHA-256 of the exact
manifest it fully validated; the core rehashes that manifest, admits only its
strict safe member records, and checks the requested file's exact size and
SHA-256 before returning a native asset. Size or modification-time changes
force content revalidation, manifest bytes are rehashed on every resolution,
and unbind changes the asset generation.

Eight store-focused production C++ tests demonstrate the positive member and
reject an unlisted member, wrong token, unsafe/duplicate records, wrong-size
content, same-size corruption, post-validation mutation, same-size manifest
mutation with restored timestamp, and generation change after unbind. The final
surfaceless/null-muted runtime proof retained the expected native TBF lifecycle
with zero fallthrough and an optical bootstrap.

This fixes corrupt-store admission; it does not prove the oracle's guest return
values or buffer effects. Those require a separate post-return IOP trace and
remain in this issue.
