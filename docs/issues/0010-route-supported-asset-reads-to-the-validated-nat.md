---
id: 10
title: Route supported asset reads to the validated native store
status: investigating
symptom: Supported AVP:E asset opens still continue into the original optical-disc path even though a validated native store exists
state_items: S023
tags: assets,ioman,native-io,loading
created: 2026-08-27
updated: 2026-08-27
---

## Scope

Claim the grounded read-only AVP:E asset namespaces at the IOP import boundary and back their descriptors with ordinary host files from the validated native store. Preserve the original path as an explicit A/B oracle.

## Acceptance

- The product and silent control runner pass only a validated store root to the core.
- Title gating, path normalization, traversal rejection, read-only flags, and missing-file errors are exercised through production policy.
- Open/read/seek/close for TBF, one movie, and one streamed-audio file match oracle bytes and short-read/error behavior.
- Claimed requests show host-file lifecycle events and no original IOP/CDVD fallback; an explicitly unclaimed bootstrap request still follows the oracle path.

### Note (2026-08-27)
2026-08-27: the validated store now claims read-only TBD, MOVIES, and STREAMS paths through NativeAssets and generic host descriptors. Two surfaceless/null-muted runs observed two TBF native opens, 41-56 reads, 67052-127138 bytes, 2-4 seeks, and one close; ELF/IRX remained unclaimed. A no-root run of the same binary produced zero native claims. Live production-policy probes refused writes/traversal/missing files and left bootstrap unhandled. Remaining: representative movie/audio runtime lifecycles, byte-level oracle differential, explicit CDVD-event absence, async/cache, and load timing.
