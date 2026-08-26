---
id: 4
title: Prove native absolute pointer movement
status: investigating
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
