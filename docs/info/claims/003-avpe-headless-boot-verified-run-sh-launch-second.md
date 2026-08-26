---
id: C003
kind: claim
status: holds
created: 2026-08-26
tags: build
depends: src/avpe/launch.py
---

## Claim

AVPE: headless boot verified - run.sh launch --seconds N boots SLUS_20147 nogui+null-audio, FMVs play, clean SIGTERM shutdown; gotchas in docs/re/headless.md

## Evidence

scratch/logs/emulog.txt (SYSTEM.CNF 1.00, FMV started/ended, 'Add 38 seconds play time to SLUS-20147', Null audio stream line)

## What would falsify it

a future pcsx2 rebase changing flag semantics or datapath layout (re-run smoke test)
