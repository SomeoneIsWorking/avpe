---
id: C025
kind: claim
status: holds
created: 2026-08-28
tags: assets,admission,integrity
depends: src/avpe/launch.py#build_environment, thirdparty/pcsx2/pcsx2/AVPE/NativeAssetStore.cpp#NativeAssetStore::Resolve, thirdparty/pcsx2/pcsx2/AVPE/NativeAssets.cpp#ResolveStoreFile
reconfirmed: 2026-08-28
verified_at: 2026-08-28 00:50:21
---

## Claim

On the launcher path, native asset resolution admits only members of the exact validated manifest whose size and content hash match at initial admission, and revalidates after a detected path, size, or modification-time change; invalid admission fails before a native claim.

## Evidence

Project eb1a779 and PCSX2 fork fd1978a: seven NativeAssetStoreTest production-path tests reject a wrong token, unlisted member, unsafe/duplicate records, wrong size, same-size corruption, post-validation mutation, exact-manifest mutation, and confirm generation change after unbind; the final surfaceless/null-muted TBF probe retained two native opens and zero fallthrough with valid inputs.

## What would falsify it

A native AVP:E asset open succeeds without the exact launcher-supplied manifest token, for an unlisted record, with wrong initial size/content, or after a detected path/size/modification-time change invalidates content; or the valid admitted TBF production path no longer opens and reads natively without fallthrough.

## Re-confirmed 2026-08-28

Reconfirmed after project eb1a779 and fork fd1978a: the final non-windowed verifier passed 67 Python/structure tests, seven NativeAssetStore production-path tests, clang-format, and clang-tidy across 23 translation units; the final surfaceless/null-muted TBF probe completed two native opens and zero original fallthrough with valid admission while bootstrap remained optical.
