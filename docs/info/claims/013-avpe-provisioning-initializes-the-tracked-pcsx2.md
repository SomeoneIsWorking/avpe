---
id: C013
kind: claim
status: holds
created: 2026-08-27
tags: dependencies,provisioning,submodule
depends: src/avpe/dependencies.py#provision_submodules, src/avpe/cli.py#main, .gitmodules
---

## Claim

AVPE provisioning initializes the tracked PCSX2 fork recursively and validates its checkout against the superproject gitlink

## Evidence

On 2026-08-27, uv run --frozen avpe provision synchronized thirdparty/pcsx2 and nested lucent, then reported PCSX2 ready at 37a1c62a9371; 16 Python/structure tests and the full non-windowed verifier passed.

## What would falsify it

Provisioning fails from an uninitialized checkout, leaves a nested dependency uninitialized, accepts a checkout whose HEAD differs from the gitlink, or requires the removed deps.toml revision field.
