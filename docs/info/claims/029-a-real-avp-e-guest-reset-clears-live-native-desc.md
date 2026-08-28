---
id: C029
kind: claim
status: holds
created: 2026-08-28
tags: assets,reset,lifecycle
depends: thirdparty/pcsx2/pcsx2/R3000A.cpp#psxReset, thirdparty/pcsx2/pcsx2/AVPE/NativeGuestReset.cpp#Handle, thirdparty/pcsx2/pcsx2/AVPE/NativeAssets.cpp#ResetGuestState, src/avpe/native_asset_probe.py#probe_native_asset_guest_reset
---

## Claim

A real AVP:E guest reset clears live native descriptors and synthetic CDVD mappings while preserving the admitted store and resuming native reads

## Evidence

Two clean surfaceless/null-muted runs used the shipping POST /guest/reset boundary while native I/O was live. The ioman leg reset from guest_reset_epoch 1 to 2 with INTRO.PSS and TBF descriptors present before reset, empty descriptors and mappings after reset, zero transient handles, and resumed INTRO.PSS reads with native_open_count 2 and zero original fallback. The CDVD leg reset with MENU01.ZIV mapped at base LSN 3758096384, exact size and SHA-256, and TBF descriptor present; after reset descriptors, mappings, and completion tokens were empty, the bounded cache was exactly 512 pages/33554432 bytes, and MENU01.ZIV resumed native sector reads with matching completion consumption and zero fallback. Both runs reported Running, surfaceless, null-muted status and unchanged isolated memory-card hashes.

## What would falsify it

A clean reset fails to advance guest_reset_epoch, retains any descriptor, mapping, or active completion token, drops the admitted store or cache bound, reopens the target without native reads, records original optical fallback, fails to resume the target read, or changes the isolated memory-card bytes.
