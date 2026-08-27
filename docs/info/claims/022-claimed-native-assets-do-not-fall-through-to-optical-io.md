---
id: C022
kind: claim
status: holds
created: 2026-08-27
tags: assets,cdvd,ioman,native-io
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeAssets.cpp#NoteOriginalFallback, thirdparty/pcsx2/pcsx2/IopBios.cpp#open_HLE, src/avpe/control_test.py#oracle_asset_fallback_is_verified
reconfirmed: 2026-08-27
verified_at: 2026-08-27 23:28:39
---

## Claim

Claimed native AVP:E assets do not return to the original IOP/CDVD implementation

## Evidence

A clean validated-store run recorded zero original fallthrough for TBF, EALOGO.PSS, FOXLOGO.PSS, ZONOLOGO.PSS, INTRO.PSS, and MENU01.ZIV while SLUS_201.47 fell through once. A no-store run of the same binary recorded two TBF fallthroughs and zero native claims. Both runs were surfaceless and null-muted and shut down normally.

## What would falsify it

a claimed TBF, movie, or stream observation records a nonzero original-fallback count, an unclaimed no-store TBF observation records no fallback, or a handled HLE import still invokes the original implementation for the same call

## Re-confirmed 2026-08-27

Fork commit 2316c91 passed 38 tests plus format/tidy; real native and no-store runs produced the required zero and positive original-fallthrough results.

## Re-confirmed 2026-08-27

2026-08-27 full gate plus fresh native byte-trace boot reconfirmed native TBF and MENU01 paths with the bootstrap remaining optical; diagnostic tracing does not change import disposition or fallthrough accounting.
