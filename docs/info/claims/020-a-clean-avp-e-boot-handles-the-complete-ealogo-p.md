---
id: C020
kind: claim
status: holds
created: 2026-08-27
tags: assets,movie,native-io
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeAssets.cpp#ResolveIomanOpen, thirdparty/pcsx2/pcsx2/IopBios.cpp#read_HLE, tools/run_control_test.py#probe_native_movie_reads
reconfirmed: 2026-08-27
verified_at: 2026-08-27 22:16:23
---

## Claim

A clean AVP:E boot handles the complete EALOGO.PSS lifecycle through the validated native asset descriptor

## Evidence

A 2026-08-27 surfaceless/null-muted CRC 64DA78A3 run with an isolated formatted-card copy recorded one native MOVIES/EALOGO.PSS open, 104 reads totaling the exact validated 1687556-byte file size, two seeks, and one close; bootstrap remained unclaimed and the TBF boundary also passed.

## What would falsify it

a clean validated-store run reads EALOGO.PSS through the optical fallback, returns a byte total other than the validated file size, fails its seek/close lifecycle, or the same trace appears without a native store

## Re-confirmed 2026-08-27

After the signed ioman read-result fix in fork commit bc15e1a, the final clean run again completed EALOGO.PSS through 104 reads totaling 1687556 bytes, two seeks, and one close.

## Re-confirmed 2026-08-27

After fork commit 2316c91, the clean stream run again completed EALOGO.PSS through 104 reads totaling 1687556 bytes, two seeks, one close, and zero original fallthrough.
