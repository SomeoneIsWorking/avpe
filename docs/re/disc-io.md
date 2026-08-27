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

## Native TBF descriptor proof

The product launcher now validates/provisions the store before setting
`AVPE_NATIVE_ASSET_ROOT`. `NativeAssets::ResolveIomanOpen` recognizes only the
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

## Native replacement requirements

The next implementation must preserve the original path as an A/B oracle and
claim only a validated, read-only namespace for this title. Before it may
replace an open it must:

- normalize the PS2 device path and reject traversal, writes, unknown devices,
  unsupported flags, and paths outside the provisioned manifest;
- validate the user-derived store against the supported disc revision without
  tracking copyrighted bytes;
- implement the existing IOP descriptor and direct CDVD sector contracts,
  including short reads, zero-tail sectors, and errors;
- prove representative TBF and streamed-audio byte slices match the oracle;
- show that claimed imports do not return to the original IOP/CDVD path, while
  a deliberately unclaimed request does.

Async host prefetch and caching belong behind `NativeAssets` after behavioral
equivalence. The synchronous game-side `CTbdFile::ReadChunk` contract must not
be mislabeled as asynchronous merely because the host backend can prefetch.
