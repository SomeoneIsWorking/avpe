---
id: I013
kind: instrument
status: trusted
created: 2026-08-27
---

## Instrument

NativeAssetByteTrace plus compare_native_asset_bytes.py canonical chunk differential

## Validated by

The production traces supplied both source answers and matched 96 canonical chunks; a copied-digest OTHER-answer control changed TBD/TBF.TBF offset 0 and the comparator rejected it at that exact path, offset, and size. Strict policy rejects wrong modes, source contamination, loss counters, conflicts, malformed digests, missing files, mismatched extents/sizes, and insufficient overlap.

## Known failure modes

The first attempted oracle hook after CDVD DMA/decryption saw only early optical
sectors and no registered asset-sector payloads, so it was removed. Reading ISO
files while original-disc playback was active also produced transient reader
failures. The accepted oracle capture runs only after the native MENU01 boundary,
and byte-trace runs cannot be reused as loading-time evidence because hashing and
ISO reads perturb cache and host time.
