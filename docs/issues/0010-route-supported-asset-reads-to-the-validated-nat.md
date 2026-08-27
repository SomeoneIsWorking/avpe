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
- Open/read/seek/close for TBF and one movie plus search/seek/sector-read for one streamed-audio file match oracle bytes and error behavior.
- Claimed requests show host-file lifecycle events and no original IOP/CDVD fallback; an explicitly unclaimed bootstrap request still follows the oracle path.

### Note (2026-08-27)
2026-08-27: the validated store claims read-only TBD and MOVIES paths through NativeAssets and generic host descriptors. Two surfaceless/null-muted runs observed two TBF native opens, 41-56 reads, 67052-127138 bytes, 2-4 seeks, and one close; ELF/IRX remained unclaimed. A no-root run of the same binary produced zero native claims. Live production-policy probes refused writes/traversal/missing files and left bootstrap unhandled. A clean boot with an isolated formatted-card copy completed EALOGO.PSS through one native open, 104 reads totaling its exact validated 1687556-byte size, two seeks, and one close; longer traces also completed FOXLOGO.PSS and ZONOLOGO.PSS. FSSOUND's separately grounded cdvdman path then completed a native MENU01.ZIV search, seek, and two reads totaling 49152 bytes. Remaining: byte-level oracle differential, async/cache, and load timing.

### Note (2026-08-27)
2026-08-27: runtime import-branch accounting replaced the inferred fallback result. A native clean boot recorded zero original fallthrough for TBF, EALOGO.PSS, the other startup movies, and MENU01.ZIV while SLUS_201.47 fell through once. A no-store run of the same binary recorded two TBF fallthroughs and zero native claims. Remaining: byte-level oracle differential, async/cache, and load timing.

### Dead end (2026-08-27)
2026-08-27: booting scratch/states/mission1.p2s with the native lifecycle probe produced zero IOP opens because the savestate resumes after file descriptors/loading state were established. It correctly failed the requirement for a fresh TBF read. Do not weaken the probe or cite savestate resume as movie/audio boundary evidence; drive an actual game transition or grounded stream-open function instead.

### Dead end (2026-08-27)
2026-08-27: calling grounded `CShell::SetNextLevel("M01/background.tbd")` from mission1.p2s safely raised the normal transition flag but still produced zero fresh opens. `CShell` reused the archive descriptor restored inside the savestate, so even a real level transition cannot turn that descriptor into native evidence. Clean boot is required for descriptor-origin proofs.
