---
id: 4
title: Prove native absolute pointer movement
status: resolved
symptom: the live rendered cursor still cannot be moved from host mouse coordinates even though the generic EE-call boundary is verified
state_items: S008
tags: input,pointer,ee-call,verification
created: 2026-08-26
updated: 2026-08-26
---

## Root cause

`Input_UpdatePositionAbsolute` expects a pointer to a guest `CInputData`
containing the requested screen coordinates. The verified shuttle currently
passes register values only; it does not yet own temporary guest argument
storage, so the host cannot safely construct that pointer argument.

## Required change

Add a dedicated `NativeInput` owner that stages temporary `CInputData` bytes in
bounded guest stack storage on the VM thread, saves and restores the overwritten
bytes, reads the live `GAvPPointer` singleton, and invokes the verified shuttle
without duplicating its register/timing machinery. This interface accepts
normalized absolute coordinates; HTTP is diagnostic plumbing, not the shipping
input owner.

## Verification

- Refuse a null or implausible live pointer and out-of-resolution coordinates.
- Capture a baseline frame, inject two deliberately distinct positions through
  the same shipping path, and capture both resulting frames.
- Prove the rendered cursor occupies two distinct expected screen regions.
- Restore the guest temporary storage exactly and show a negative request does
  not mutate cursor or stack state.

## Resolution

`NativeInput::MoveAbsolute` now owns normalized-coordinate validation,
resolution and singleton checks, absolute selector mode, and the game-native
update call. `EECallShuttle::CallWithStackBuffer` stages the exact eight-byte
argument inside a saved 0x20-byte o32 frame and verifies byte-exact restoration.

The first implementation exposed two root causes during the real gate:
`vtlb_V2P` depends on an optional PCSX2 map absent for this title, and nested
recompiler execution overwrote the normal dispatcher's global jump buffer.
The final path validates the direct low-main-RAM stack range and interprets
synthetic calls with an independent jump buffer while scheduler events remain
owned by the interrupted outer execution.

The isolated surfaceless/muted runner rendered stable cursor centers at
`(128.48,95.06)` and `(512.35,94.71)`, attested exact restoration at the same
nonzero staging address, rejected `(1.25,0.2)` with HTTP 400, retained the
second cursor position, and then shut down normally. Claim C009 records the
evidence.
