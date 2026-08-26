---
id: C009
kind: claim
status: holds
created: 2026-08-26
tags: input,pointer,verification
depends: tools/run_control_test.py#probe_native_pointer
---

## Claim

The AVPE native input bridge moves the live rendered game cursor to distinct
absolute host targets through the game's own selector and update functions,
without pad-axis emulation, direct position writes, or persistent guest-stack
mutation.

## Evidence

Through the C007 isolated runtime and I002 snapshot detector, normalized
targets for screen positions `(128,96)` and `(512,96)` produced game-observed
fields `(127.999992,96)` and `(511.999969,96)`, then stable rendered centers
`(128.48,95.06)` and `(512.35,94.71)`. Both responses reported restored
temporary stack storage at the same nonzero address. A request outside the
normalized range returned HTTP 400; two later coherent snapshots retained the
second cursor position. The process then completed graceful shutdown with exit
status zero.

Per-run proof: `scratch/control-test/pointer-proof.json` and its three BMPs are
ignored artifacts. The durable implementation and falsifier are
`NativeInput.cpp`, `EECallShuttle.cpp`, `tools/run_control_test.py`, and I002.

## What would falsify it

A supported mission position fails to follow a valid normalized target, a
rejected request changes the cursor or guest stack, stack restoration differs
by any byte, the bridge requires a virtual pad path, or repeated calls corrupt
the interrupted EE scheduler/context or prevent graceful shutdown.
