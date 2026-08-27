---
id: 11
title: Replace FSSOUND direct CDVD stream reads
status: resolved
symptom: AVP:E streamed VAG/ZIV audio bypasses the native ioman descriptor seam and still reads sectors through cdvdman
state_items: S023
tags: assets,audio,cdvd,native-io
created: 2026-08-27
updated: 2026-08-27
---

## Scope

Replace FSSOUND.IRX stream search/seek/read calls at the cdvdman import boundary with validated host-file sectors while preserving unrecognized CDVD traffic as the oracle.

## Acceptance

- The clean-room contract for StreamPlay, StreamSetup, and StreamRead is recorded from the user-derived FSSOUND.IRX.
- Only validated STREAMS/*.VAG and STREAMS/*.ZIV searches receive native handles; unknown paths and ordinary CDVD calls remain unhandled.
- Native sector reads preserve 2048-byte sector, zero-tail, seek, error, and wrap behavior.
- A surfaceless/null-muted run records a real stream search and nonzero native bytes without an optical fallback for that stream.

## Evidence

FSSOUND.IRX static RE grounded `StreamPlay` (`0x00000CAC`), `StreamSetup`
(`0x00001F98`), `StreamRead` (`0x000028A8`), and `StreamThreadLoop`
(`0x00003A30`). The module imports `sceCdSearchFile`, `sceCdSeek`, and
`sceCdRead` directly from cdvdman and retains the returned LSN and byte size.

The title-gated HLE maps validated VAG/ZIV files into reserved synthetic LSNs,
preserves 2048-byte sector buffers with a zero tail, and claims only mapped
seek/read calls. A 2026-08-27 clean surfaceless/null-muted run reached
`STREAMS/MENU01.ZIV` through one native search/open, one seek, and two reads
totaling 49,152 bytes. The game bootstrap remained unclaimed and the isolated
card source and working copy retained the same SHA-256.

### Resolution (2026-08-27)
Grounded FSSOUND's direct cdvdman contract, mapped only validated VAG/ZIV files to bounded synthetic LSNs, and reproduced MENU01.ZIV through one native search, one seek, and 49152 bytes in a clean surfaceless/null-muted run.
