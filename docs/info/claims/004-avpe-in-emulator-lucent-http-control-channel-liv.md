---
id: C004
kind: claim
status: holds
created: 2026-08-26
tags: instrument
depends: thirdparty/pcsx2#AVPE.cpp
---

## Claim

AVPE: in-emulator lucent HTTP control channel live (fork 794cba0, lucent af80097) - status/memread byte-exact vs ELF/stateload+save round-trip verified on SLUS-20147 boot

## Evidence

docs/re/control-channel.md; scratch/logs/launch-avpe3.log; scratch/states/title.p2s

## What would falsify it

any endpoint returning stale/wrong bytes after a pcsx2 rebase; re-verify with tools/avpe_http.py memread vs file offsets
