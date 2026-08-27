---
id: C021
kind: claim
status: holds
created: 2026-08-27
tags: assets,audio,cdvd,native-io
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeAssets.cpp#ResolveCdvdSearch, thirdparty/pcsx2/pcsx2/IopBios.cpp#searchFile_HLE, tools/run_control_test.py#probe_native_stream_reads
reconfirmed: 2026-08-27
verified_at: 2026-08-27 22:16:23
---

## Claim

FSSOUND menu audio uses validated native host sectors through its direct cdvdman boundary

## Evidence

A 2026-08-27 clean CRC 64DA78A3 run recorded one native STREAMS/MENU01.ZIV search/open, one seek, and two reads totaling 49,152 bytes, exactly 24 2048-byte sectors. The process was surfaceless and null-muted, bootstrap stayed unclaimed, shutdown was graceful, and the isolated card remained byte-identical.

## What would falsify it

a clean validated-store run reaches optical CDVD handling for MENU01.ZIV, returns non-sector-shaped bytes or a different stream mapping, claims an ordinary real-disc LSN, or produces the same native evidence without the validated store

## Re-confirmed 2026-08-27

Fork commit bc15e1a passed the full gate and a final clean run reproduced one MENU01.ZIV native search, one seek, and 49152 bytes with bootstrap unclaimed.

## Re-confirmed 2026-08-27

After fork commit 2316c91, the clean run reproduced MENU01.ZIV native search/seek/read with 32768 bytes at acceptance and zero original cdvdman fallthrough.
