---
id: 18
title: Provision the project dependency prefix from the launcher
status: investigating
symptom: A fresh checkout has no scratch/deps Qt prefix, so prepare refuses before configuring the AVPE target
state_items: S012
tags: launcher,dependencies,qt,provisioning
created: 2026-08-28
updated: 2026-08-28
---

## Root cause

The launcher knows the vendored PCSX2 dependency workflow but does not invoke
it; `scratch/deps` is treated as a pre-existing developer artifact.

## What was tried / dead ends

The workflow is vendor-owned and already contains the authoritative source
versions, hashes, and build flags. Duplicating its dependency list in AVPE
would create a second authority.

## Resolution

`src/avpe/dependency_prefix.py` now selects the tracked Linux or macOS PCSX2
dependency workflow, runs it in `scratch/` with `BUILD_FFMPEG=0`, refuses
missing build tools with a platform-specific package command, and validates
the resulting Qt prefix. `prepare_product()` invokes this owner before
configuring AVPE. The vendor workflow remains the authority for source
versions, hashes, and dependency build flags.

The command path is covered by positive and negative tests. A complete cold
download/build is still an outstanding cross-platform verification gap.

### Note (2026-08-28)
Implemented the Python owner and wired it into prepare_product. This session verified workflow selection, exact scratch working directory, BUILD_FFMPEG=0 propagation, post-run Qt-prefix validation, and DNF refusal behavior with tests. The real checkout already has a complete prefix, so a destructive cold download/build has not been run; keep this issue investigating until that path is exercised on supported hosts.
