---
id: C007
kind: claim
status: holds
created: 2026-08-26
tags: build,test,host
depends: tools/run_control_test.py
---

## Claim

AVPE's dedicated control-test runner boots the target without access to the
desktop or an audio device and accepts success only after the child reports the
actual surfaceless and null-muted runtime state for the same nonce.

## Evidence

The verified run reported host mode `control-test`, surface `surfaceless`,
audio `null-muted`, serial `SLUS-20147`, and CRC `64DA78A3` on its reserved port
and nonce. `emulog.txt` independently recorded
`acquireRenderWindow(... surfaceless=true)`, `Creating Null audio stream`, the
same serial/CRC, and graceful VM shutdown. The current nine-test non-windowed
suite includes negative surface, audio, and nonce cases, product-profile
isolation, the launch environment contract, and the first-party source
structure cap.

## What would falsify it

A run maps any native window, touches a real audio backend, accepts another
process or stale binary, mutates the product profile, fails to reach the target,
or requires signal-driven cleanup.
