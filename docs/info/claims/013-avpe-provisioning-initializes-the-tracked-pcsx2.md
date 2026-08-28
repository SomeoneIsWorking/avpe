---
id: C013
kind: claim
status: holds
created: 2026-08-27
tags: dependencies,provisioning,submodule
depends: src/avpe/cli.py#main
reconfirmed: 2026-08-28
verified_at: 2026-08-28 21:25:18
---

## Claim

AVPE provisioning initializes the tracked PCSX2 fork recursively and validates its checkout against the superproject gitlink

## Evidence

On 2026-08-27, uv run --frozen avpe provision synchronized thirdparty/pcsx2 and nested lucent, then reported PCSX2 ready at 37a1c62a9371; 16 Python/structure tests and the full non-windowed verifier passed.

## What would falsify it

Provisioning fails from an uninitialized checkout, leaves a nested dependency uninitialized, accepts a checkout whose HEAD differs from the gitlink, or requires the removed deps.toml revision field.

## Re-confirmed 2026-08-27

2026-08-27: after adding the assets CLI branch, the provisioning tests still passed recursive sync/init, revision extraction, and exact gitlink readiness; project-state and the full verifier passed

## Re-confirmed 2026-08-28

The real Synchronizing submodule url for 'thirdparty/pcsx2'
Synchronizing submodule url for 'thirdparty/pcsx2/3rdparty/lucent'
[avpe][info][provision] PCSX2 ready at 286f5cb2f0dd command completed successfully on the current checkout, synchronized the tracked PCSX2 and nested lucent submodules, and reported PCSX2 ready at 286f5cb2f0dd. The full non-windowed verifier also passed 110 Python tests and structure checks.
