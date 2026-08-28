---
id: C030
kind: claim
status: holds
created: 2026-08-28
tags: input,camera,minimap,selector
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeCameraInput.cpp#Apply, thirdparty/pcsx2/pcsx2/AVPE/NativeCameraRoute.cpp#Handle, src/avpe/native_camera_probe.py#probe_native_camera
---

## Claim

AVP:E's original camera move, minimap zoom, and minimap pan callbacks change
their guest-owned state through the native EE-call boundary while retaining
exact stack state and absolute pointer selector mode

## Evidence

The clean `mission1.p2s` run invoked `POST /input/camera` for move `(1,0)`,
zoom `(1,0)`, and rotate `(0.2,0)`. Move changed camera `+0x158/+0x15c` from
`[0,0]` to `[25,0]` and left the live pointer input type at `1`; zoom changed
the minimap mode to true and initialized its cursor and camera-pointer fields;
rotate changed the minimap cursor from `101.826050` to `102.492546` and the
derived camera pointer from `179.370483` to `180.544540`. All three calls
reported `stack_restored=true`, positive EE cycle counts, and unchanged camera,
pointer, and minimap singleton identities. The run reported `Running`,
`surfaceless`, `null-muted`, and `SLUS-20147`.

## What would falsify it

A fresh mission-state run returns success without the documented guest-owned
field changes, reports a changed singleton identity, fails exact stack
restoration, leaves pointer input type other than `1` after move, or routes the
callbacks through pad-state emulation rather than the original AVP:E functions.
