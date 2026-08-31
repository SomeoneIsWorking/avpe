---
id: 12
title: Collapse supported asset operations to host-disk completion
status: investigating
symptom: Startup native I/O is byte-equivalent, bounded, and faster, but the representative M1 transition lacks automated no-optical and exact ShellLoadLevel timing proof
state_items: S024
tags: assets,cache,loading,timing
created: 2026-08-27
updated: 2026-08-30
---

## Scope

Automate a clean-boot `CShell::SetNextLevel` transition into M1 and measure the
exact `CShell::ShellLoadLevel` entry-to-return interval. Every supported
asset operation in that interval must complete through `NativeAssets` at
host-storage/cache speed rather than emulated CDVD seek, sector-ready, or
transfer timing. Preserve validated bytes and exercised guest success
semantics, fail closed before a native claim when the store cannot serve a
request, and keep byte tracing disabled during timing.

## Acceptance

- Clean-boot M1 automation uses no input savestate or pad injection and proves
  the exact staged `SetNextLevel` request plus pre/post transition state. Menu
  keyboard/mouse delivery remains independently owned by issue #6.
- Exact `ShellLoadLevel` entry/return boundaries and the supported operation
  backend trace are captured.
- Supported interval operations have zero original IOP/CDVD fallthrough and
  zero optical timing waits; bootstrap and unsupported traffic remain
  separately identified.
- At least three alternating clean oracle/native mission pairs report guest
  cycles/frames and secondary host elapsed time with identity, boundary,
  spread, and no-reduction controls.
- Existing cache bounds, byte differential, surfaceless/null-muted isolation,
  and card hashes remain valid.

## Timing evidence

On project `8fcf8d1` and PCSX2 fork `e8c7af9`, the dedicated timing tool ran
`1:oracle, 1:native, 2:oracle, 2:native, 3:oracle, 3:native` against
SLUS-20147 CRC `64DA78A3`. Every sample used the first `TBD/TBF.TBF` open as
ordinal 1 and the seek immediately after `STREAMS/MENU01.ZIV` search as ordinal
3. Actual TBF and MENU01-seek backends matched each declared mode.

| Pair | Mode | EE cycles | IOP cycles | Frames | Host elapsed ns |
|---:|---|---:|---:|---:|---:|
| 1 | oracle | 40,408,849,912 | 5,051,106,429 | 8,213 | 137,019,880,383 |
| 1 | native | 35,312,223,239 | 4,414,027,549 | 7,178 | 120,056,785,587 |
| 2 | oracle | 40,408,849,912 | 5,051,106,429 | 8,213 | 137,020,742,427 |
| 2 | native | 35,312,223,239 | 4,414,027,549 | 7,178 | 120,081,436,193 |
| 3 | oracle | 40,408,849,912 | 5,051,106,429 | 8,213 | 137,020,964,076 |
| 3 | native | 35,312,223,239 | 4,414,027,549 | 7,178 | 120,072,932,485 |

| Metric | Oracle median | Native median | Oracle spread | Native spread | Reduction |
|---|---:|---:|---:|---:|---:|
| EE cycles | 40,408,849,912 | 35,312,223,239 | 0 | 0 | 5,096,626,673 (12.6126%) |
| IOP cycles | 5,051,106,429 | 4,414,027,549 | 0 | 0 | 637,078,880 (12.6127%) |
| Frames | 8,213 | 7,178 | 0 | 0 | 1,035 (12.6020%) |
| Host elapsed ns | 137,020,742,427 | 120,072,932,485 | 1,083,693 | 24,650,606 | 16,947,809,942 (12.3688%) |

The binary SHA-256 was
`d877a65b734fd9aae4e4ca9460c6e61c5f4deba5b8cd117a548ec10021f8cb9b`;
the source CHD SHA-256 was
`b9165e126aeb7154d95f17d2dea21c21d7754f2480e3fae5217dcdf55155e9a0`.
All samples had the same emulation-relevant configuration, byte tracing was
disabled, status was surfaceless/null-muted, and the isolated card source and
working copy stayed at
`55237edfb8bd977e22ecf84ae2d1a942f8167fd3cbf9798376259342120f2b2b`.
Copied ordinal-drift and no-reduction controls were both rejected. Detailed
ignored evidence is
`scratch/control-test/load-timing-refresh-210/asset-load-timing-comparison.json`.

## Remaining

- Capture the completed mission boundary through the optical oracle with the
  same title-modal completion policy.
- Prove supported operations inside the full entry-to-return interval never
  enter optical timing or original IOP/CDVD delivery on the native leg.
- Run and compare three alternating clean oracle/native mission pairs.

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

After landing, fresh clean captures on project `89cc05a` and fork `c0c6611`
matched the ISO oracle for all 96 canonical chunks across TBF, EALOGO,
FOXLOGO, ZONOLOGO, INTRO, and MENU01 through the shared cache. The copied
digest control was rejected at TBF offset zero, and both source/working card
pairs remained byte-identical.

Guest reset closes ioman descriptors before clearing synthetic mappings while
keeping the admitted store. Shutdown and actual disc-epoch changes close
native descriptors before cache/store unbind. Save-state format version 1
records exact native descriptor slots, cursor, admitted identity, and synthetic
LSN mappings, and restore fails closed if those identities cannot be admitted.
This path builds and passes the scoped linter. A pre-change version-0 pause-menu
state loaded successfully after the version plumbing fix. A new version-1
clean-boot state then saved and reloaded into the same running
surfaceless/null-muted target. Two later clean runs exercised the live state:
`INTRO.PSS` restored at the exact descriptor slot and cursor before advancing
without a reopen, and `MENU01.ZIV` restored its exact mapping identity and LSN
allocator before advancing native sector reads and matching completion
consumption. Both runs had zero native fallback and byte-identical card copies.
Resolved issue #14 records the live recovery proof.

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

This establishes fail-closed admission for the PC-native path. Exhaustive
emulated optical-error return/buffer parity is not an acceptance condition for
disc-operation collapse; title-observed failure tracing is issue #16.

### Dead end (2026-08-28)
The legacy scratch/states/mission1.p2s snapshot is not native mission-load evidence: a surfaceless/null-muted run with the admitted native store restored native_asset_state.descriptors=[] and cdvd_mappings=[], and /assets/opens stayed empty. It was captured before the native boundary existed, so clean boot is required for descriptor-origin and mission-transition proof.

### Note (2026-08-28)
A 90-second clean boot was still inside `INTRO.PSS`, so issuing
`SetNextLevel` before the startup stream boundary did not reach the normal
`CShell::MainLoop` consumer. The successful clean proof waits for native
`STREAMS/MENU01.ZIV` readiness, then stages `M01/background.tbd` through the
grounded `SetNextLevel` ABI and observes the populated M1 world. The proof is
recorded in `scratch/control-test/native-marine-m1-transition-proof.json`.

### Finding (2026-08-28)
Ghidra disassembly of the supported ELF grounds `ShellLoadLevel` at
`0x0016F910`, its `CTbdFile::Load` call at `0x0016FA44`, and the first
post-load instruction at `0x0016FA4C`; its return instruction is
`0x0016FAD4`. `MainLoop` calls it at `0x0016F784` and resumes its loop at
`0x0016F744`. Fresh mission-timing runs armed these grounded addresses and
captured the exact `M01/background.tbd` entry, but captured no post-load point
within 240 seconds on either the optical oracle or native leg; an optical
oracle run was extended to 600 seconds with the same result. The M1 world
endpoint still appeared and the clean transition proof remained valid. The
timing callback seam therefore needs a recompiler execution-boundary fix (or
a title-grounded completion event), not another guessed guest address. No
mission timing pair is claimed until that boundary is observed on both legs.

### Finding (2026-08-30)

The recompiler seam now instruments the exact grounded entry and post-load
continuation permanently, with runtime arming. A valid Clang-built
surfaceless/native mission run still did not reach `0x0016FA4C` within the
120-second capture, but it also did not hang in one TBF chunk: the bounded
observer recorded 124 `CTbdFile::ReadChunk` starts, 124 completions, and 124
callbacks to `GMissionGoalsMenu::LoadHackCallback` (`0x00204AC0`), with no
`CTbdFile::Error`. A repeat accounted 4,029,554 payload bytes across those 124
chunks, with an 868,004-byte maximum, a 228-byte final chunk, and zero
multi-slice chunks. The earlier `litodp`/`__pack_d` timeout samples are loading
icon timer conversions under that callback, not a formatting-loop failure.
This narrows the missing timing proof to title-owned post-read finalization
after the early world endpoint; it does not justify a larger guessed timeout
or a native timing claim.

### Finding (2026-08-30, archive reads finish before the long wait)

The earlier count-only result did not show one `ReadChunk` per host second.
Dividing 124 completed chunks by the later 120-second boundary timeout conflated
a completed burst with the post-read wait. The grounded timing observer now
records first/last chunk points and aggregate chunk, callback,
payload/decompression, and inter-chunk clocks. A valid native run completed all
124 chunks from 443471480200970 to 443472644934231 host ns: 1.164733261 s and
67 frames. Chunk bodies accounted for 0.435780112 s/25 frames; 123 gaps
accounted for 0.728953149 s/42 frames. Callback and payload intervals were
0.022820176 s and 0.388417553 s respectively. All sequence counters were zero,
all 4,029,554 bytes were accounted, and no loader error occurred.

The 120-second missing-return interval therefore begins after the final
`ReadChunk`; it is not native-storage throughput, a stuck chunk, callback
pacing, or inter-chunk pacing. Static `CTbdFile::LoadCore` places the next
candidate boundary at EOF finalization: the `_WatchCount` gate followed by
`FixupOffsets`, `FixupExterns`, `SetupPublics`, `FixupHandles`, and `InitTypes`.
The next observation must classify those title-owned phases before any backend
performance claim is extended.

The phase observer now does so without instrumenting the hot `_WatchCount`
loop. A valid clean run recorded 22 ordered rounds through `FixupHandles`, but
only 21 `InitTypes` completions and `LoadCore` returns. A bounded parent-stage
stack modeled the nested `LoadCore` called from the final outer `InitTypes`;
the trace ended at depth zero, next expected `init_types_complete`, with zero
sequence errors. The active boundary is therefore the outer `InitTypes`
indirect initializer call at `0x0017467C`, after its nested archive load, not
any native asset operation.

### Finding (2026-08-30, mission return and modal root cause)

Stack-aware initializer observation identified the active outer call as
`CPresetFillData`; object-factory observation then identified
`GExitMissionGoalsButton::Create`. Static RE showed its constructor enters the
synchronous `GMissionGoalsMenu::LoadHackCallback` loop while the menu singleton
is live. That loop polls `GInputDevice` directly before the menu reaches the
normal callback registry, so the missing return was a title-owned modal waiting
for Exit activation, not storage throughput or an unfinished nested archive.

The runtime bridge now pumps pending host CPU transactions only at the exact
modal loop PC. `NativeMenuInput` validates the mission menu singleton/vtable,
waits for the unique exact Exit-button vtable, invokes its exact focus virtual,
and calls `GMenu::Input(Activate)` synchronously. Deferred dispatch is invalid
at this reentrant seam because the original guest block can revisit the same PC
and falsely satisfy the deferred return test.

A clean native run reached `ShellLoadLevel` continuation `0x0016FA4C` with no
loader error. It completed 134/134 observed chunks (124 payload chunks), all 24
post-read rounds, 2,638/2,638 initializer calls/returns, and 942/942 object
factory calls/returns with zero sequence errors. The exact Exit object was
focused and activated with exact stack restoration, and the mission menu
singleton cleared. This closes the native missing-boundary investigation. The
issue remains open for interval-wide no-optical proof and three alternating
oracle/native mission timing pairs.

### Finding (2026-08-31, timing probe instrumentation regression)

The first two clean mission-timing attempts reached the `TBD/TBF.TBF` start
boundary but did not reach `STREAMS/MENU01.ZIV` within 210 seconds. This was
repeatable after unrelated host compiler work finished. The cause was the
fork's unresolved-IOP-import instrumentation: every control-test boot enabled
`NativeBiosTrace`, so the new recompiler fallback traced every unresolved import
even when the requested probe was load timing. The timing launcher now disables
that diagnostic explicitly with `AVPE_BIOS_TRACE=0`; ordinary control tests and
explicit BIOS probes retain tracing. A rebuilt Clang binary is ready for one
fresh mission comparison; no timing result is claimed until that comparison
completes.
