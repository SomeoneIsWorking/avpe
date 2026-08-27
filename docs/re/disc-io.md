# AVP:E disc and native asset I/O

This document records the grounded asset boundary for the supported
`SLUS-20147` executable. The current implementation claims validated read-only
asset paths while leaving the original IOP behavior available as the oracle.

## Game-side archive path

AVP:E's world and UI data is primarily one indexed RIFF archive rather than a
loose-file tree:

| Address | Function | Grounded role |
|---|---|---|
| `0x0010C8D0` | `CZFile::Open` | Select the platform device and open a game file. |
| `0x0010CB00` | `CZFile::Read` | Read through the selected platform owner. |
| `0x0010CBE0` | `CZFile::Seek` | Seek through the selected platform owner. |
| `0x0016C1D0` | `CZRiffFile::Open` | Open a `CZFile` and validate the RIFF `FORM`. |
| `0x0016C2C0` | `CZRiffFile::Duplicate` | Duplicate an already-open RIFF view. |
| `0x0016C3A0` | `CZRiffFile::Descend` | Enter a requested RIFF chunk/list. |
| `0x0016C500` | `CZRiffFile::Seek` | Seek within the RIFF view. |
| `0x0016C550` | `CZRiffFile::Read` | Read within the RIFF view. |
| `0x00173AE0` | `CTbdFile::LoadTbffIndex` | Open `tbf.tbf`, descend `FORM/TBFF/INDX`, and build the lookup table. |
| `0x00173CB0` | `CTbdFile::ReadChunk` | Read/decompress a chunk synchronously in pieces no larger than 1 MiB. |
| `0x00173E60` | `CTbdFile::Load` | Resolve the uppercase normalized name by CRC and select archive or loose fallback. |
| `0x00173FC0` | `CTbdFile::LoadCore` | Load the typed TBD chunks into regular or platform memory. |

`CShell::ShellLoadLevel` at `0x0016F910` first requests `master.tbd` and then
the selected level. `CTbdFile::Load` uppercases and normalizes the requested
name, computes its CRC32, and looks it up in the `TBF.TBF` `INDX` hash table.
A hit duplicates the global RIFF view, seeks directly to the indexed offset,
and descends the embedded `LIST/TBD2` record. A miss first tries `%08X.tbx`
and then the original loose filename.

The loader recognizes `TEMP/TEMX`, `DATA/DATX`, `PLAT/PLAX`, `EXTA`, `HNDL`,
`EXTN`, `PUBL`, `OFFS`, and `TYPE` chunks. Compressed chunks use the game's BWJ
decompressor. Movies (`MOVIES/*.PSS`) and streamed `.VAG`/`.ZIV` audio are
separate file consumers. Movies use the EE file-I/O path, while FSSOUND.IRX
accesses audio sectors directly through `cdvdman`; both paths are now traced
below.

The movie path is a second game-side file wrapper over the same IOP boundary:

| Address | Function | Grounded role |
|---|---|---|
| `0x00180730` | `PS2_PlayMovie` | Initialize the PS2 movie stack, run the MPEG reader, and restore GS state. |
| `0x00180D70` | `readMpeg` | Fill/demux the PSS ring and optionally abort on a grounded controller edge after frame 10. |
| `0x00181870` | `strFileOpen` | Build `cdrom0:\\MOVIES\\<name>;1`, then call `sceOpen`/`sceLseek`. |
| `0x001819B0` | `strFileClose` | Close the movie descriptor through `sceClose`. |
| `0x001819D0` | `strFileRead` | Read movie bytes through the EE file-I/O RPC path. |

The user-derived `IRX/FSSOUND.IRX` has a separate sector-oriented contract:

| Address | Function | Grounded role |
|---|---|---|
| `0x00000CAC` | `StreamPlay` | Read a 32-byte EE filename and build `\\STREAMS\\%s;1`. |
| `0x00001F98` | `StreamSetup` | Call `sceCdSearchFile`, retain returned LSN/size, seek, then read 8 mono or 16 stereo sectors for the initial SPU fill. |
| `0x000028A8` | `StreamRead` | Read 4 mono or 8 stereo sectors, advance the sector cursor, zero the 16 KiB buffer on error, and wrap after the returned file size. |
| `0x00003A30` | `StreamThreadLoop` | Drive the stream update/read loop. |

Those functions import `sceCdRead`, `sceCdSeek`, and `sceCdSearchFile`
directly from `cdvdman`; they never cross ioman. The returned file size and
2048-byte sector geometry are therefore part of the replacement contract.

## Emulator interception boundary

PCSX2 recognizes IOP import stubs in both execution engines:

- `R3000AInterpreter.cpp::psxJ` calls `irxImportExec` for an import-table jump.
- `x86/iR3000A.cpp::psxRecompileIrxImport` emits the equivalent HLE call.
- `IopBios.cpp::irxImportHLE` maps `ioman` and `iomanX` imports 4–16, including
  open, close, read, and lseek.
- The same dispatcher maps only FSSOUND's grounded `cdvdman` imports 6, 7, and
  10 (read, seek, and search) into the AVP:E title owner. Ordinary LSNs and
  non-stream searches still return unhandled and continue into the oracle.
- `R3000A::ioman::open_HLE` returns zero for an unclaimed device, causing the
  original IOP implementation to continue. Existing host-managed descriptors
  already implement the corresponding close/read/lseek lifecycle.

These are the narrow replacement seams: `IopBios.cpp` delegates title-specific
policy to `AVPE::NativeAssets`; it does not own the AVP:E namespace or asset
store. Intercepting here can bypass the low-level CDVD scheduler and its
optical seek/sector-ready timing. Accelerating `CDVDSECTORREADY_INT` or caching
CHD sectors would retain the wrong ownership and timing model.

## Runtime proof

`NativeAssets::ResolveIomanOpen` records at most 128 unique paths only when the
surfaceless control-test mode is active and the disc serial is `SLUS-20147`.
The boundary-observation probe removes the native-store environment so every
request remains on the oracle path. `GET /assets/opens` exposes a snapshot to
the diagnostic transport, and
`tools/run_control_test.py --probe-native-assets` validates it.

The 2026-08-27 proof booted CRC `64DA78A3` with no display access and null-muted
audio. It observed 15 opens and 14 unique paths with no dropped records,
including:

- `cdrom0:/TBD/23ACA1AA.TBX;1`;
- `cdrom0:/TBD/NOMEMLOGO.TBD;1`;
- two opens of `cdrom0:/TBD/TBF.TBF;1`;
- the game ELF, `IOPRP242.IMG`, and the title's IRX modules.

The same probe required the deliberately absent
`__avpe_absent_asset__` sentinel to have zero observations. This demonstrates
both answers from the instrument. The loose fallback probes are real runtime
behavior and correct the earlier archive-only static picture.

## Validated native store

`avpe assets` now provisions the store through three independent owners:

- `raw_sector.strip_image` stream-converts the CHD-extracted 2352-byte sectors
  to address-stable 2048-byte blocks and reports every sector form;
- `IsoImage` strictly validates both-endian ISO9660 fields, extents, directory
  records, duplicate case-insensitive paths, and bounded extraction;
- `provision_native_assets` validates exact supported-revision anchors, hashes
  every extracted file into a versioned manifest, revalidates the complete
  store, and atomically renames it out of scoped staging.

The supported disc yielded 268,924 MODE2 Form1 sectors, 137 files, and
550,353,354 extracted bytes. `SYSTEM.CNF`, `SLUS_201.47`, and `TBD/TBF.TBF`
are revision anchors. The manifest and bytes live only below ignored
`scratch/native-assets/avpe-native-assets-v1/`; no game data is tracked.
Wrong identity, missing validated files, malformed ISO metadata, bad sector
sync, and a distinct Form2 layout are negative controls. Runtime redirection
must consume only this validated store; merely pointing the core at an
arbitrary host directory is not acceptable.

The launcher therefore passes two coupled values: the `files/` root and the
SHA-256 of the exact manifest that completed full Python validation.
`NativeAssetStore` rehashes the sibling manifest before binding, strictly
parses its schema and safe case-insensitive file index, and resolves only listed
members. Before a member is returned it canonicalizes the recorded spelling
beneath the files root and validates exact size and SHA-256. Content validation
is retained only while canonical path, size, and modification time are stable;
manifest bytes are rehashed on each resolution. Missing members are distinct
from an invalid store, and unbinding invalidates the asset generation.

The production implementation's eight store-focused C++ tests demonstrate both valid and
invalid outcomes: unlisted paths, a wrong admission digest, unsafe or duplicate
records, wrong-size content, same-size corrupt content, mutation after a valid
resolution, exact-manifest mutation with a restored timestamp, and generation
change after unbind. This closes store admission before a native claim. It does
not yet prove native/oracle guest return values and buffer effects after an IOP
operation; that remains S024 work.

## Native TBF descriptor proof

The product launcher now validates/provisions the store before setting
`AVPE_NATIVE_ASSET_ROOT` and its exact manifest admission digest.
`NativeAssets::ResolveIomanOpen` recognizes only the
supported title and the read-only `TBD/`, `MOVIES/`, and `STREAMS/` namespaces;
it uppercases disc paths, strips the exact `;1` version, rejects unsafe
components, canonicalizes beneath the store root, and requires its sibling
manifest. `IopBios` then opens the resolved path through the existing generic
host descriptor and records the original disc path for lifecycle attribution.

In the native proof, `TBF.TBF` produced two native opens, 41–56 reads,
67,052–127,138 returned bytes, 2–4 seeks, and one close before the snapshot.
The early missing TBX/TBD fallbacks were refused as missing. ELF and IRX paths
were outside the claimed namespaces and stayed on the original implementation.
Removing the native root from the same binary yielded zero native claims for
all observed paths, including both TBF opens.

The diagnostic policy probe calls the production resolver and separately
demonstrates: native TBF read, refused write, refused traversal, refused missing
file, and unhandled bootstrap. This is a partial S023 proof; it does not yet
stand in for byte-level oracle comparison.

`tools/run_control_test.py --probe-native-movie-reads` extends that proof from
a clean boot with an isolated copy of a formatted card. It requires the exact
complete `MOVIES/EALOGO.PSS` lifecycle: one native open, 104 reads totaling the
validated file size of 1,687,556 bytes, two seeks, and one close. The 2026-08-27
run passed surfaceless and null-muted. Longer observation also captured complete
native `FOXLOGO.PSS` and `ZONOLOGO.PSS` lifecycles and an in-progress native
`INTRO.PSS` lifecycle. A no-card run instead entered `NOMEMLOGO.TBD`, so the
probe now names its temporary formatted-card precondition until native saves
remove it.

## Native streamed-audio sector proof

`NativeAssets::ResolveCdvdSearch` claims only validated `STREAMS/*.VAG` and
`STREAMS/*.ZIV` files. It returns an LSN from a reserved synthetic range tied
to that host file and its exact byte size. Only seeks and bounded reads wholly
inside a live synthetic mapping are claimed; ordinary real-disc LSNs remain
unhandled. Reads preserve the 2048-byte sector shape and zero-fill the final
partial sector, while the game retains its grounded file-size wrap policy.

`tools/run_control_test.py --probe-native-stream-reads` performed a clean
2026-08-27 boot with the isolated formatted-card copy. It reached
`STREAMS/MENU01.ZIV`, recorded one native search/open, one seek, and two native
sector reads totaling 49,152 bytes. The byte count is exactly 24 sectors. The
same trace retained zero native claims for `SLUS_201.47`, while TBF and all four
startup movies used native storage. The process reported surfaceless,
null-muted operation, shut down normally, and left the source and working card
hashes identical.

The import wrappers also record the branch taken after resolution rather than
inferring it from I/O totals. In the native clean boot, TBF, all four movies,
and `MENU01.ZIV` recorded zero returns to the original implementation, while
`SLUS_201.47` recorded one. In a no-store run of the same binary, both TBF
opens recorded original fallthrough and zero native claims. A handled import
returns directly to the guest, so the original IOP/CDVD implementation and its
sector scheduler cannot execute for that claimed call.

## Live native save-state recovery

PCSX2's HLE save-state owner remains authoritative for native descriptor and
synthetic-CDVD serialization. `NativeAssetStateSnapshot` is a diagnostic view
captured on the CPU thread immediately before `/state/save` serialization and
immediately after successful `/state/load`; it reports native guest fd, path,
cursor, exact CDVD mapping identity and LSN allocation, and transient
completion-token occupancy. It does not serialize a second copy of that state.

Two clean surfaceless/null-muted probes exercised the production boundary. The
ioman leg saved `INTRO.PSS` at fd 257/cursor 131,072, allowed reads to advance,
loaded the state, observed the exact descriptor snapshot, and then advanced
reads again without another native open or original fallback. The CDVD leg
saved `MENU01.ZIV` with its exact path, base LSN 3,758,096,384, size 7,602,176,
SHA-256, and next LSN 3,758,100,096; after load the same mapping resumed sector
reads and matching one-shot completion consumption with no reopen, fallback,
rejection, or pending token. Both copied cards remained byte-identical.
Strengthened reruns also required the post-load runtime to report Running,
surfaceless, and null-muted, plus a bounded-cache snapshot with zero transient
host handles. The CDVD leg reached the exact 512-page/32 MiB resident bound and
continued correctly through eviction.

The policy rejects a snapshot with an active completion token, descriptor or
mapping drift after load, a post-load reopen, original fallback, or missing
read/completion progress. Per-run states and JSON proofs are ignored under
`scratch/control-test/`.

## Native/ISO byte differential

`NativeAssetByteTrace` is a separate diagnostic owner. In `native` mode it
assembles the first 16 canonical 2048-byte file-relative chunks from the actual
ioman buffers and synthetic cdvdman sectors, independent of guest read-call
boundaries. In `oracle` mode it captures the same chunks through PCSX2's
existing `IsoReader` only after the native MENU01 stream boundary has been
reached. The two sources therefore do not read one another's buffers, and no
game bytes are persisted—only paths, extents, sizes, and SHA-256 digests.

Two clean surfaceless/null-muted runs on SLUS-20147 CRC 64DA78A3 matched all 16
chunks for each of `TBF.TBF`, `EALOGO.PSS`, `FOXLOGO.PSS`, `ZONOLOGO.PSS`,
`INTRO.PSS`, and `MENU01.ZIV`: 96 exact matches, zero mismatches, identical ISO
extents/sizes, and zero drops or conflicts. Both isolated-card hashes remained
unchanged. `tools/compare_native_asset_bytes.py` also changes one digest in a
copy of the native artifact and requires rejection at the exact path, offset,
and size; the 2026-08-27 control rejected `TBF.TBF` offset 0, size 2048.

An attempted post-DMA optical capture in `cdvdReadSector()` was falsified and
removed. It saw 1,379 early optical sectors but no asset sectors after the
corresponding opens registered, so it could not serve as the file-byte oracle.
Reading whole files through `IsoReader` concurrently with active original-disc
playback also produced transient reader failures. Oracle capture is therefore
deferred until the native menu-stream boundary, and byte tracing is never used
for loading-time evidence.

## Native load-timing differential

`NativeLoadTiming` is independent of the byte tracer. With
`AVPE_LOAD_TIMING=oracle|native`, it starts at the first supported
`TBD/TBF.TBF` open before backend selection and ends at the `sceCdSeek`
immediately following the supported `STREAMS/MENU01.ZIV` search. It records EE
cycles, IOP cycles, guest frames, secondary steady-clock nanoseconds, event
ordinals, and the actual backend selected at both ends. A snapshot is complete
only when both backends match the declared mode, counters increase, no search
intervenes, the target is recognized, control-test mode is surfaceless, and
`AVPE_ASSET_BYTE_TRACE` is absent.

`tools/compare_native_load_timing.py` runs clean samples serially in alternating
oracle/native order. It requires at least three equal sample sets, recomputes
every delta from endpoints, rejects ordinal drift, bounds EE/IOP spread to 1%,
frame spread to one, and host spread to 25%, and requires a positive reduction
for every metric. It also pins clean project/fork revisions, binary and source
disc hashes, the complete emulation-relevant config, and isolated-card hashes.
Qt window geometry/state and game-list header values are excluded from config
identity because the diagnostic frontend rewrites those non-emulation layout
fields under `-nogui`; a regression proves that an emulation-setting change is
still detected.

The 2026-08-28 run used project `edbfda4`, fork `87608f3`, SLUS-20147 CRC
`64DA78A3`, and order oracle/native repeated three times. Every sample used
boundary ordinals 1→3.

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

Every run reported the expected actual backends, surfaceless/null-muted status,
disabled byte tracing, the same binary/disc/config identity, and an unchanged
isolated card. A copied sample with a changed end ordinal was rejected for
boundary drift. Raising copied native EE values to the optical baseline was
rejected for no measured reduction, so the comparator demonstrated both
answers.

This timing evidence proves only the startup TBF-open→post-MENU01-search seek
reduction. Cache bounds have separate evidence below; this timing run does not
establish cold/warm behavior, failure equivalence, or a representative mission
transition.

## Bounded native cache and lifecycle

Both claimed delivery paths now enter `NativeAssets::Read` with an admitted
store record. `NativeAssetCache` owns immutable 64 KiB pages keyed by store
generation, record ID, and page index. Its true-LRU capacity is exactly 512
pages/32 MiB; a source operation coalesces at most 16 consecutive missing pages
and opens at most one transient host stream. Only a complete coalesced read
installs pages, so failed and partial fills cannot poison later hits.

`NativeAssetFile` implements the ioman `IOManFile` contract as a record plus
per-descriptor cursor. It has no persistent OS file descriptor. FSSOUND's
synthetic CDVD mappings retain the same admitted record and use the same cache,
including the original final-sector zero tail. Store validation remains the
identity authority before every cache read.

Guest reset ordering is descriptor close followed by synthetic-mapping reset;
the admitted store and reusable pages remain bound. VM shutdown and an actual
disc-epoch change selectively close native descriptors, reset mappings, and
then unbind cache and store. An unexpected in-process root, token, or manifest
change blocks rebinding until that explicit teardown, preventing old guest
handles from crossing store generations.

Save-state version 1 includes exact native descriptor indices, cursor and
admitted size/hash identity, plus each synthetic guest path, LSN, size, and
hash. Restore re-resolves every path through the admitted store and fails the
whole state load on identity, descriptor-slot, seek, range, or overlap failure.
The previous version-0 HostFS representation remains readable, but it cannot
contain this unreleased native-host schema.

The disk loader now passes the archive's checked version into `memLoadingState`;
previously it always exposed the current build version to conditional readers.
A real pre-change version-0 pause-menu state loaded after that correction. A
new version-1 clean-boot state also saved, reported `0x9A590001`, reloaded, and
returned to the same running surfaceless/null-muted target.

The production cache tests demonstrate byte reuse and the opposite outcomes
for short read, EOF, failed fill/retry, capacity eviction, and generation
change. The surfaceless/null-muted runtime cache probe observed four fills,
54 hits, four resident pages (262,144 bytes), one peak transient handle, and
zero live handles after the TBF startup reads. A live reset/save-state
round-trip with an active native descriptor or synthetic mapping is still
required; build and unit evidence do not prove that recovery path.

Fresh post-landing oracle/native captures on project `89cc05a` and fork
`c0c6611` passed all 96 canonical chunk comparisons across TBF, EALOGO,
FOXLOGO, ZONOLOGO, INTRO, and MENU01 through the shared cache. The deliberate
TBF digest mismatch was rejected at offset zero, both runs remained
surfaceless/null-muted, and both isolated card copies retained their source
SHA-256.

## Native replacement invariants

The native path preserves the original source as an A/B oracle and claims only
a validated, read-only namespace for this title. It must continue to:

- normalize the PS2 device path and reject traversal, writes, unknown devices,
  unsupported flags, and paths outside the provisioned manifest;
- validate the user-derived store against the supported disc revision without
  tracking copyrighted bytes;
- implement the existing IOP descriptor and direct CDVD sector contracts,
  including short reads, zero-tail sectors, and errors;
- keep a claimed FSSOUND sector read and its immediate `sceCdGetError` under
  one native backend: a fixed-capacity one-shot token is keyed by the caller's
  IOP stack, distinct stacks cannot consume each other's result, and a missing
  token leaves unrelated cdvdman calls on the oracle;
- prove representative TBF and streamed-audio byte slices match the oracle;
- show that claimed imports do not return to the original IOP/CDVD path, while
  a deliberately unclaimed request does.

Any future asynchronous prefetch belongs behind `NativeAssetCache` and must
preserve the same bounds and failure semantics. The synchronous game-side
`CTbdFile::ReadChunk` contract must not be mislabeled as asynchronous merely
because the host backend can prefetch.

## Native cdvdman completion ownership

FSSOUND calls `sceCdGetError` immediately after its direct `sceCdRead` calls.
Leaving import index 8 unhandled after claiming index 6 made the result depend
on cdvdman's unrelated optical-controller error state. `NativeCdvdCompletion`
now records the native read result against the caller's IOP stack and consumes
it exactly once for the matching `sceCdGetError`; a caller without a token is
left on the original cdvdman path. The token store is fixed at 16 entries,
never evicts a live caller, reports rejected records, and resets with native
guest state.

A clean surfaceless/null-muted MENU01 run recorded two claimed sector reads and
two matching result consumptions, with zero rejected records and zero active
tokens. The same trace counted unrelated token misses, demonstrating that the
HLE did not swallow general cdvdman error queries. The isolated card source and
working copy retained SHA-256
`55237edfb8bd977e22ecf84ae2d1a942f8167fd3cbf9798376259342120f2b2b`.
