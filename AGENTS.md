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
- `NativeConfig.*` owns the immutable typed AVP:E environment snapshot. Product
  subsystems consume its narrow accessors and never read process environment
  state directly.
- `NativeInput.*` owns gameplay pointer and button semantics.
- `NativeMenuInput.*` owns callback-registry menu discovery, synchronous
  mission-goals modal focus, and invocation of AVP:E keyboard and pointer actions.
- `NativeMenuItems.*` owns bounded menu-descendant traversal, activation-hotkey
  and focused-item callback admission, attract-owner exclusion, and exact
  mission-goals Exit-item discovery. It reads guest state but never invokes actions.
- `NativeAttractInput.*` owns exact registered attract-button cancellation
  admission; `NativeMenuInput` composes it before requiring a menu. The guest
  callback owns the complete next-level and attract-owner teardown lifecycle.
- `NativeMovieInput.*` owns one-shot movie cancellation admission and readiness.
  EE hooks only observe player/MPEG lifetime; the host input poll dispatches the
  original abort function through the deferred shuttle. CPU reset and savestate
  preparation discard pending input. The guest retains all movie teardown.
- `EECallShuttle.*` owns deferred request admission separately from guest
  context installation. `VMManager::Execute` brackets its safe outer execution
  boundary; event callbacks never install a deferred EE call mid-interrupt.
  CPU reset and savestate preparation own cancellation of shuttle state.
- `NativeInputCallbacks.h` owns the shared callback descriptor layout, bounded
  discovery access contract, and admitted target value; it owns no action policy.
- `NativeMenuRoute.*` owns only the diagnostic HTTP parsing, status mapping,
  typed menu/movie endpoint dispatch, and JSON presentation for native-menu
  state and actions.
- `NativePadReadiness.*` owns validated read-only observation of the title's
  CPS2Input initialization and report readiness. Diagnostic menu admission
  consumes it; it does not initialize controllers or own menu actions.
- `NativeTitleTransition.*` owns passive, exact-PC observation of the
  title-to-profile handoff. It neither sends input nor mutates guest/profile
  state; `NativeTitleTransitionRoute.*` owns its diagnostic HTTP presentation.
- `NativeEeExecutionHooks.*` composes AVPE's narrow EE instruction observers;
  the interpreter and recompiler call this owner rather than individual
  diagnostic modules.
- `NativeIopExecutionHooks.*` composes the exact IOP caller-return observation
  for oracle import result pairing. The recompiler instruments only return
  blocks admitted by `NativeIopReturnSites`; the interpreter consults that
  exact registry only while an oracle call is pending.
- `NativeIopReturnSites.*` owns the fixed process-lifetime atomic registry of
  exact IOP caller return PCs. It owns no trace events or import policy.
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
  admission, coalescing, serialization, and exact EE BIOS and IOP oracle
  entry/return pairing. `NativeBiosTrace.*` owns trace lifecycle, pending-call
  state, and grounded mission progress/boundary capture, and composes the event
  store under its trace lock.
- `NativeGameSaveBoundary.*` owns the exact normal `CProfile::SaveGame`
  entry/return observation, including capture scoping from the validated
  profile object through its final `jr ra`. It is diagnostic-only and does not
  define menu input or native-save behavior.
- `src/avpe/native_game_load_probe.py` owns the surfaceless normal-load proof
  policy from the live Pause menu through the exact `CProfile::LoadGame`
  boundary and synchronous mission-goals modal. It does not own menu input,
  firmware semantics, or the native-save backend.
- `NativeMemoryCardState.*` owns the CPU-thread diagnostic snapshot of slot
  presence, savestate auto-eject countdown, busy state, and derived readiness.
  It does not mutate card state or own title save policy.
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
