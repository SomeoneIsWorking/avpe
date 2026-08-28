---
id: 19
title: Implement native camera and minimap input boundary
status: resolved
symptom: The port has grounded camera and minimap functions but no native PC input path
state_items: S011
tags: input,camera,minimap,selector,re
created: 2026-08-28
updated: 2026-08-28
---

## Root cause

AVP:E exposes camera movement through registered gamepad callbacks, while the
host previously routed only pointer and menu actions. The camera and minimap
functions require the guest-owned CInputData ABI and must be called through the
EE shuttle.

## Current work

Added a dedicated NativeCameraInput owner, shared float-pair staging, host
held-key and wheel translation, and a surfaceless control route.

## Verification

The camera probe verifies the before/after guest-owned fields and writes the
ignored proof artifact described in the resolution. Windowed event delivery is
tracked separately as the explicit S011 gap.

### Resolution (2026-08-28)
Implemented NativeCameraInput with shared CInputData staging, original AVP:E camera/minimap callback dispatch, selector/minimap state capture, host held-key and wheel routing, and POST /input/camera. The exact live mission-state proof is recorded in scratch/control-test/native-camera-proof.json and S011 remains partial only because the user-visible window route is not exercised by surfaceless agent tests.
