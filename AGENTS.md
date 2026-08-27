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
- `NativeAssets.*` owns title gating, the AVP:E disc namespace, native-store
  policy, ioman host-file replacement, and FSSOUND's direct cdvdman sector
  mapping. `IopBios.cpp` provides only grounded narrow hooks; it must not
  absorb game paths, manifests, or cache policy, and ordinary disc traffic
  remains on the emulator oracle.
- `NativeAssetByteTrace.*` owns bounded canonical-chunk assembly and ISO-oracle
  byte evidence. `AVPE.cpp` only exposes its diagnostic snapshot/capture routes;
  byte tracing is never used for timing evidence.
- `src/avpe/native_assets.py`, `iso9660.py`, and `raw_sector.py` own native
  asset-store provisioning. Derived game bytes stay under ignored `scratch/`;
  only the schema, identity anchors, validation logic, and tests are tracked.
- `thirdparty/pcsx2/pcsx2-avpe/HostInputRouter.*` owns product key-to-action
  and mouse-to-action policy; `HostWindow.*` owns only platform event capture
  and window lifecycle.
  Neither may emulate keyboard/mouse as a DualShock.
- `thirdparty/pcsx2/pcsx2-avpe/` is the standalone product frontend. It links
  the `PCSX2` emulation-core library but never the `pcsx2-qt` application or
  its `MainWindow`, game list, debugger, dialogs, or settings UI.
- `AVPE.cpp` owns the diagnostic control transport only. Its routes may carry
  proof intent but do not define shipping input policy.

Agent runtime tests use `tools/run_control_test.py` only. They remain surfaceless
and null-muted; `run.sh` is the user's product launcher.
