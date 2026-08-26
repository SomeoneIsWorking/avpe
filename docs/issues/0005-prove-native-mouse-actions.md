---
id: 5
title: Prove native mouse selection and command actions
status: investigating
symptom: absolute pointer movement is verified but host mouse buttons do not yet invoke selection or contextual commands
state_items: S009,S010
tags: input,mouse,selection,command
created: 2026-08-27
updated: 2026-08-27
---

## Root cause

`NativeInput` currently owns movement only. The mapped game handlers for left
press/release and right release are not exposed through that owner, so native
host button intent cannot reach `SelectChanging` or `CommandMove`.

## Required change

Extend `NativeInput` with typed button-edge operations which validate the live
pointer and invoke `Input_PressMouse1`, `Input_ReleaseMouse1`, and
`Input_ReleaseMouse2` through the existing transaction/shuttle boundary.
Diagnostic HTTP routes may carry proof traffic but must not own mouse policy.

## Verification

- A left press/release pair changes selection through the game handler and a
  differing negative position does not select the same target.
- Right release at a valid world target reaches `CommandMove` and produces an
  observable squad-command effect.
- Invalid pointer state and invalid edge sequences fail explicitly.
- Repeated actions preserve the interrupted guest context and complete
  graceful surfaceless shutdown.
