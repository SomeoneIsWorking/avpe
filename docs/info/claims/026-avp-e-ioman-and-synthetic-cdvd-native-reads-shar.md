---
id: C026
kind: claim
status: holds
created: 2026-08-28
tags: assets,cache,loading
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeAssetCache.cpp#NativeAssetCache::ReadAt, thirdparty/pcsx2/pcsx2/AVPE/NativeAssetFile.cpp#Open, thirdparty/pcsx2/pcsx2/AVPE/NativeAssets.cpp#Read, src/avpe/native_asset_cache_probe.py#cache_snapshot_is_verified
---

## Claim

AVP:E ioman and synthetic-CDVD native reads share an exact 32 MiB bounded cache with no persistent host file handles.

## Evidence

Thirteen production tests passed, including failed-fill retry, exact capacity, true LRU, and generation invalidation. A surfaceless/null-muted boot observed 4 fills, 54 hits, 4 resident 64 KiB pages, one peak transient handle, and zero live handles after 53 native TBF reads.

## What would falsify it

A native read bypasses NativeAssetCache, resident pages or bytes exceed 512 pages/32 MiB, an ioman descriptor retains a host file handle, a failed fill becomes a hit, or the live probe cannot produce both cache activity and the bounded opposite outcomes.
