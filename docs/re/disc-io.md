# AVP:E disc and native asset I/O

This document records the grounded asset boundary for the supported
`SLUS-20147` executable. The current implementation observes requests without
claiming them, so the original IOP and CDVD behavior remains the oracle while
the native store and replacement reader are built.

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
separate file consumers and still need representative runtime traces.

## Emulator interception boundary

PCSX2 recognizes IOP import stubs in both execution engines:

- `R3000AInterpreter.cpp::psxJ` calls `irxImportExec` for an import-table jump.
- `x86/iR3000A.cpp::psxRecompileIrxImport` emits the equivalent HLE call.
- `IopBios.cpp::irxImportHLE` maps `ioman` and `iomanX` imports 4–16, including
  open, close, read, and lseek.
- `R3000A::ioman::open_HLE` returns zero for an unclaimed device, causing the
  original IOP implementation to continue. Existing host-managed descriptors
  already implement the corresponding close/read/lseek lifecycle.

This is the narrow replacement seam: `IopBios.cpp` delegates title-specific
policy to `AVPE::NativeAssets`; it must not learn the AVP:E namespace or asset
store. Intercepting here can bypass the low-level CDVD scheduler and its
optical seek/sector-ready timing. Accelerating `CDVDSECTORREADY_INT` or caching
CHD sectors would retain the wrong ownership and timing model.

## Runtime proof

`NativeAssets::ObserveIomanOpen` currently records at most 128 unique paths
only when the surfaceless control-test mode is active and the disc serial is
`SLUS-20147`. It never claims an open. `GET /assets/opens` exposes a snapshot to
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

## Native replacement requirements

The next implementation must preserve the original path as an A/B oracle and
claim only a validated, read-only namespace for this title. Before it may
replace an open it must:

- normalize the PS2 device path and reject traversal, writes, unknown devices,
  unsupported flags, and paths outside the provisioned manifest;
- validate the user-derived store against the supported disc revision without
  tracking copyrighted bytes;
- implement the existing IOP descriptor read, seek, close, short-read, and
  error contracts through host files;
- prove representative TBF, movie, and streamed-audio bytes match the oracle;
- show that claimed reads no longer produce CDVD sector/timing events, while a
  deliberately unclaimed request still exercises the original path.

Async host prefetch and caching belong behind `NativeAssets` after behavioral
equivalence. The synchronous game-side `CTbdFile::ReadChunk` contract must not
be mislabeled as asynchronous merely because the host backend can prefetch.
