# AVPE project-specific architecture

Shared agent policy and reusable workflows come from the canonical `re-harness`
skills repository. This file records only how the port architecture applies to
AVP:E.

Dusklight is the ownership reference for host-side port structure. Follow its
separation between platform event translation, typed input policy, game-facing
behavior, and UI ownership; do not copy its platform-specific implementation.

- `thirdparty/pcsx2/pcsx2/AVPE/GuestObjects.*` owns validated reads of AVP:E
  guest objects and handles.
- `NativePointerMotion.*` owns shared normalized-coordinate validation,
  resolution lookup, guest staging, and absolute pointer movement.
- `NativeInput.*` owns gameplay pointer and button semantics.
- `NativeMenuInput.*` owns discovery and invocation of AVP:E keyboard and
  pointer menu actions.
- `thirdparty/pcsx2/pcsx2-qt/AVPE/HostInputRouter.*` owns product key-to-action
  and mouse-to-action policy; `HostWindow.*` owns only platform event capture
  and window lifecycle.
  Neither may emulate keyboard/mouse as a DualShock.
- `AVPE.cpp` owns the diagnostic control transport only. Its routes may carry
  proof intent but do not define shipping input policy.

Agent runtime tests use `tools/run_control_test.py` only. They remain surfaceless
and null-muted; `run.sh` is the user's product launcher.
