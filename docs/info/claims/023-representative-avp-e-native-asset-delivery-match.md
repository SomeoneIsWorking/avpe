---
id: C023
kind: claim
status: holds
created: 2026-08-27
tags: assets,native-io,oracle
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeAssetByteTrace.cpp#CaptureIsoOracle, src/avpe/asset_byte_compare.py#compare_asset_byte_traces
reconfirmed: 2026-08-27
verified_at: 2026-08-27 23:28:39
---

## Claim

Representative AVP:E native asset delivery matches the PCSX2 ISO oracle for six startup files

## Evidence

Two clean surfaceless/null-muted runs on SLUS-20147 CRC 64DA78A3 produced matching ISO extent, file size, and all 16 canonical 2048-byte SHA-256 chunks for TBF.TBF, EALOGO.PSS, FOXLOGO.PSS, ZONOLOGO.PSS, INTRO.PSS, and MENU01.ZIV: 96 matched chunks and zero mismatches. Both isolated-card hashes remained unchanged; scratch/control-test/asset-byte-comparison.json is ignored per-run detail.

## What would falsify it

a native and ISO-oracle trace from the same supported disc reports a mismatched canonical chunk, extent, or file size; records are dropped or conflicted; or either source is found to hash bytes from the other source

## Re-confirmed 2026-08-27

2026-08-27 final CPU-thread ISO-oracle rerun matched the existing native delivery trace across 96/96 canonical chunks; the forced copied-digest control rejected TBD/TBF.TBF offset 0 size 2048, and all 51 tests, clang-format, and clang-tidy passed.
