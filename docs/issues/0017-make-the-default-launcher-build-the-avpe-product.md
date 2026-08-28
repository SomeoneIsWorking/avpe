---
id: 17
title: Make the default launcher build the AVPE product
status: resolved
symptom: A cold or partially built checkout reaches launch with no scratch/build/bin/avpe and refuses instead of preparing the configured product target
state_items: S012
tags: launcher,build,provisioning,G001
created: 2026-08-28
updated: 2026-08-28
---

## Root cause

The launcher only checks for the product executable. It has no owned
configure/build preparation path.

## What was tried / dead ends

The existing PCSX2 workflow establishes the CMake/Ninja contract and requires
the project-owned `scratch/deps` prefix. Rebuilding that dependency stack is
outside this slice.

## Resolution

### Note (2026-08-28)
Added `src/avpe/build.py` and `./run.sh prepare`. The default launch path now
calls the same preparation owner before entering launch. Existing product
binaries are checked through the current CMake target: configured trees rebuild
incrementally and a missing build tree is configured before rebuilding. Unit
tests cover command construction, stale-binary prevention, incomplete-prefix
refusal, and Fedora/Debian/macOS installation hints. The remaining S012 gap is
provisioning the project-owned Qt/dependency prefix on a fresh checkout.
