---
id: C006
kind: claim
status: holds
created: 2026-08-26
tags: re
depends: docs/re/input-path.md
---

## Claim

AVPE: mission reached + cursor located - M1 loads via start-presses; live cursor is GMarinePointer (vptr 0x3388A0) at pThe__11GAvPPointer; pos floats (329,233)=center confirmed at obj+0x194/198; writing screen-pos floats (incl mirrors +0x188) does NOT move sprite - renders from world pos, so EE-call shuttle invoking Input_UpdatePositionAbsolute is required

## Evidence

scratch/re/c1.png c2.png g1.png b.png; /snap endpoint; states/mission1.p2s

## What would falsify it

if writing world-pos fields directly moves the sprite, shuttle is optional; if UpdatePositionAbsolute also fails to move it, the render path uses yet another field
