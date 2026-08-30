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
- `NativeMenuInput.*` owns callback-registry menu discovery, the synchronous
  mission-goals load modal's exact Exit-item discovery/focus, and invocation
  of AVP:E keyboard and pointer menu actions.
- `NativeMenuRoute.*` owns only the diagnostic HTTP parsing, status mapping,
  and JSON presentation for typed native-menu state and actions.
- `NativeEeExecutionHooks.*` composes AVPE's narrow EE instruction observers;
  the interpreter and recompiler call this owner rather than individual
  diagnostic modules.
- `NativeHostYield.*` owns demand-driven host CPU event pumping at the exact
  AVP:E mission-goals modal loop. It does not own menu policy or guest actions.
- `NativeAssets.*` owns title gating, the AVP:E disc namespace, ioman host-file
  replacement, FSSOUND's direct cdvdman sector mapping, and store/cache
  lifecycle composition.
  `NativeAssetStore.*` is its private peer for exact manifest admission,
  member lookup, content validation, and generation-safe asset identity.
  `NativeAssetCache.*` owns the bounded immutable-page LRU and transient host
  reads; `NativeAssetFile.*` owns only the per-descriptor guest cursor adapter.
  `NativeCdvdCompletion.*` owns bounded one-shot pairing between a claimed
  FSSOUND sector read and the matching caller's immediate `sceCdGetError`.
  Native descriptors and synthetic CDVD mappings are frozen by PCSX2's HLE
  handle save-state owner. `NativeAssetStateSnapshot.*` only exposes an atomic
  CPU-thread description of that production state for save/load diagnostics;
  it does not own serialization.
  `IopBios.cpp` provides only grounded narrow hooks; it must not absorb game
  paths, manifests, or cache policy, and ordinary disc traffic remains on the
  emulator oracle.
- `NativeAssetByteTrace.*` owns bounded canonical-chunk assembly and ISO-oracle
  byte evidence. `AVPE.cpp` only exposes its diagnostic snapshot/capture routes;
  byte tracing is never used for timing evidence.
- `NativeLoadTiming.*` owns the grounded TBF-open through post-MENU01-search
  seek boundary, actual-backend identity, and guest/host timing capture.
  `AVPE.cpp` only exposes its snapshot route; timing runs keep byte tracing
  disabled.
- `NativeBiosEventStore.*` owns bounded sequence-ordered BIOS/IOP event
  admission, coalescing, serialization, and exact EE BIOS entry/return
  pairing. `NativeBiosTrace.*` owns trace lifecycle and grounded mission
  progress/boundary capture, and composes the event store under its trace lock.
- `src/avpe/native_assets.py`, `iso9660.py`, and `raw_sector.py` own native
  asset-store provisioning. Derived game bytes stay under ignored `scratch/`;
  only the schema, identity anchors, validation logic, and tests are tracked.
- `src/avpe/bios_inventory.py` owns deterministic summaries of captured BIOS/IOP
  traces; `tools/analyze_bios_traces.py` is only its JSON-file CLI and must not
  infer service calls that are absent from the trace.
- `src/avpe/save_format.py` owns the grounded BWJ decoder and fixed game-save
  prefix parser; `tools/analyze_save_records.py` is only its JSON-file CLI.
  This is save-format evidence, not the native-save backend and not permission
  to infer game-object meanings that have not been decoded.
- `src/avpe/native_asset_cache_probe.py` owns the bounded-cache evidence
  policy; `tools/run_control_test.py` only orchestrates its surfaceless probe.
- `src/avpe/native_asset_probe.py` owns native asset lifecycle, byte/timing
  polling, and live save/load recovery proof policy; the runner only selects
  and reports those surfaceless probes.
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
