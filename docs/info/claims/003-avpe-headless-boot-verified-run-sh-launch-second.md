---
id: C003
kind: claim
status: falsified
created: 2026-08-26
tags: build
depends: src/avpe/launch.py
---

## Claim

AVPE: `run.sh launch --seconds N` with `-nogui` was claimed to boot SLUS-20147
without a mapped window while using null audio.

## Evidence

scratch/logs/emulog.txt (SYSTEM.CNF 1.00, FMV started/ended, 'Add 38 seconds play time to SLUS-20147', Null audio stream line)

## Falsified by

The user observed the PCSX2 game window during an agent test on 2026-08-26.
Code inspection confirmed that `-nogui` hides the main UI but still lets
`MainWindow::acquireRenderWindow()` create `DisplaySurface`. The old evidence
proved boot and null audio only; it never measured native window creation.

## What would falsify it

a future pcsx2 rebase changing flag semantics or datapath layout (re-run smoke test)
