---
id: C027
kind: claim
status: holds
created: 2026-08-28
tags: assets,cdvd,native-io
depends: thirdparty/pcsx2/pcsx2/IopBios.cpp#cdvdman::getError_HLE, thirdparty/pcsx2/pcsx2/AVPE/NativeCdvdCompletion.cpp#Consume
---

## Claim

FSSOUND native sector reads keep completion ownership through the matching immediate sceCdGetError instead of consulting stale optical-controller state

## Evidence

NativeCdvdCompletion production tests covered same-stack one-shot consumption, wrong-stack isolation, two-stack interleaving, replacement, bounded-capacity rejection, and reset. A clean surfaceless/null-muted native stream run observed MENU01.ZIV search/seek plus two native reads, completion counters recorded=2 consumed=2 rejected_records=0 active_tokens=0, and unchanged card SHA-256; unrelated GetError calls produced consume misses and continued to the original cdvdman path.

## What would falsify it

A claimed native CDVD read is followed by an optical/stale sceCdGetError result, a token is consumed by the wrong caller stack, a clean stream run rejects or strands a completion, or the cited import/token code changes without re-verification
