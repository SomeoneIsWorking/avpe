---
id: C005
kind: claim
status: holds
created: 2026-08-26
tags: instrument
depends: thirdparty/pcsx2#PadDualshock2.cpp
---

## Claim

AVPE: pad injection proven into game memory - /input/press -> GetButtons clears wire bits (ACTIVE-LOW; OR was silent no-op) -> game btnword @CPS2Input+0x43e reads f7bf for start,cross. Menu-advance reaction not yet visually confirmed

## Evidence

scratch/logs/launch-nav25.log watch output: fifo=ff735af7bf... btn=f7bf while inj=0840

## What would falsify it

if a real controller pressing start does NOT advance the title screen, the game consumes buttons elsewhere and this path is insufficient for menu nav
