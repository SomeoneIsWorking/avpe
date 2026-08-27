---
id: C019
kind: claim
status: holds
created: 2026-08-27
tags: assets,native-io,ioman
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeAssets.cpp#ResolveIomanOpen, thirdparty/pcsx2/pcsx2/IopBios.cpp#open_HLE, src/avpe/control_test.py#native_asset_reads_are_verified
reconfirmed: 2026-08-27
verified_at: 2026-08-27 23:28:39
---

## Claim

With the validated store enabled, AVP:E's boot-time TBF lifecycle is handled by a native host descriptor while ELF/IRX bootstrap remains on the original IOP oracle

## Evidence

Two 2026-08-27 surfaceless/null-muted CRC 64DA78A3 runs used the same binary: native mode recorded two TBF native opens, 41-56 host reads, 67052-127138 bytes, 2-4 seeks, and one close while SLUS_201.47 and IRX opens had zero native claims; oracle mode removed AVPE_NATIVE_ASSET_ROOT and all 15 opens, including both TBF opens, had zero native claims. Production policy probes returned native-file, refused-access for write/traversal, refused-missing, and unhandled bootstrap as expected.

## What would falsify it

the same validated-store run reaches the original IOP/CDVD implementation for a claimed TBF descriptor, reads different bytes than its validated file, or the no-root oracle run still claims a native asset

## Re-confirmed 2026-08-27

2026-08-27: after final resolver traversal refusal, live policy route, product environment, and descriptor lifecycle edits, a fresh surfaceless/null-muted native-root run passed with two TBF native opens, 41 reads, 67052 bytes, two seeks, one close, zero bootstrap claims, and all five policy outcomes; the no-root run of the same binary retained zero native claims; 32 tests plus clang-format/clang-tidy passed

## Re-confirmed 2026-08-27

After fork commit bc15e1a, the final clean surfaceless/null-muted stream run reconfirmed native TBF reads and zero bootstrap claims; the 36-test format/tidy gate passed.

## Re-confirmed 2026-08-27

Fork commit 2316c91 and the 38-test full gate reconfirmed native TBF reads with zero original fallthrough; the no-store control recorded two TBF fallthroughs and zero native claims.

## Re-confirmed 2026-08-27

2026-08-27 full 51-test/format/tidy gate and fresh native byte-trace boot reconfirmed native TBF opens/reads with exact ISO-matching chunks; the only NativeAssets change registers diagnostic extents when byte tracing is explicitly enabled.
