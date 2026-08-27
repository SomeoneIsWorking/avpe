---
id: 9
title: Map and prove native asset I/O boundary
status: investigating
symptom: AVP:E asset reads still traverse emulated optical-disc I/O and timing
state_items: S021
tags: assets,disc,ioman,loading,re
created: 2026-08-27
updated: 2026-08-27
---

## Scope

Prove the title-specific high-level file boundary used by AVP:E assets, then replace supported read-only `cdrom0:` paths with validated host-backed files without retaining CDVD sector timing.

## Current evidence

Static RE shows the game opens `TBD/TBF.TBF` through `CZFile`/`CZRiffFile`, indexes embedded records by uppercase CRC, and reads/decompresses chunks synchronously. PCSX2 routes IOP `ioman`/`iomanX` imports through `R3000A::ioman::open_HLE()` in both interpreter and recompiler modes, with an explicit not-handled return to the original IOP implementation.

## Acceptance

- A silent surfaceless run records the actual AVP:E `cdrom0:` open paths at the IOP import boundary.
- The instrument demonstrates both observed and absent-path outcomes.
- Native redirection is title-gated, read-only, traversal-safe, and bypasses CDVD sector timing.
- The native and original paths are behaviorally compared for representative TBF, movie, and streamed-audio reads.

### Note (2026-08-27)
2026-08-27: added the observation-only NativeAssets owner at the shared ioman/iomanX open HLE seam. A surfaceless/null-muted CRC 64DA78A3 boot observed 15 opens (14 unique), including loose TBX/TBD probes and two TBF.TBF opens; the absent sentinel remained at zero. This proves the boot archive open boundary but not yet read/seek/close, movies, streams, native replacement, or absence of CDVD events.
