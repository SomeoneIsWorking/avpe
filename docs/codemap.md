# AVPE codemap

AVPE is organized as a native product host backed by a maintained PCSX2 fork,
with locked Python provisioning and test orchestration. The standalone product
frontend lives in the fork's `pcsx2-avpe` module; Python orchestration lives in
`src/avpe/`; emulator-thread control and native guest integration live in
`thirdparty/pcsx2/pcsx2/AVPE/`; reverse-engineering knowledge and evidence live
under `docs/`.

Project intent is in [`project-goals.md`](project-goals.md), capability state is
in [`project-state.md`](project-state.md), and atomic work is in
[`issues/`](issues/). This file owns subsystem placement only.

## Ownership map

| Subsystem | Responsibility | Current or target location | Entry point | Deep doc |
|---|---|---|---|---|
| Launcher shim | Stable locked-environment entry | `run.sh` | `uv run --frozen avpe` | — |
| CLI orchestration | User commands, environment discovery, preflight | `src/avpe/cli.py` | `main()` | — |
| Product preparation | Tracked-submodule readiness, build-tool refusal, CMake configuration, and standalone `avpe` target build | `src/avpe/build.py` | `prepare_product()` | — |
| Dependency provisioning | PCSX2 gitlink inspection plus recursive submodule initialization; dependency provenance | `src/avpe/dependencies.py`, `.gitmodules`, `deps.toml` | `provision_submodules()` | — |
| Dependency-prefix provisioning | Selects and invokes the tracked PCSX2 Qt/dependency workflow under top-level `build/`, with tool checks and post-build prefix validation | `src/avpe/dependency_prefix.py`, `thirdparty/pcsx2/.github/workflows/scripts/` | `provision_dependency_prefix()` | — |
| Product launch | Native-store validation, AVPE host argv/environment, product config, process lifetime | `src/avpe/launch.py` | `launch()` | — |
| Standalone frontend runtime | Product process composition, PCSX2 core thread/lifecycle, and host callbacks | `thirdparty/pcsx2/pcsx2-avpe/Runtime.*`, `EmulationThread.*`, `HostServices.cpp`, `Main.cpp` | `avpe` executable | [presentation](host/presentation.md) |
| Native host shell | Sole visible top-level window, render-surface lifecycle, resize/fullscreen, focus, product shutdown | `thirdparty/pcsx2/pcsx2-avpe/HostWindow.*`, `RenderSurface.*`, `NativeWindow.*` | `AVPE::HostWindow` | [presentation](host/presentation.md) |
| Product input routing | Qt key and mouse translation, held-input ownership across menu/game transitions, dispatch-bound menu pointer movement, wheel translation, and typed action dispatch | `thirdparty/pcsx2/pcsx2-avpe/HostInputRouter.*`, `HostWindow.*` | `AVPE::HostInputRouter` | [input path](re/input-path.md) |
| Presentation bridge | GS-to-host window acquisition and narrow display/settings control | `thirdparty/pcsx2/pcsx2-avpe/HostServices.cpp`, `Runtime.*` | `Host::AcquireRenderWindow()` | [presentation](host/presentation.md) |
| Control-test runner | Silent surfaceless PCSX2 process, isolated profile/card working copies, observed pad-hold and card-readiness lifecycles, loopback transport, timebox, exact process-group cleanup | `tools/run_control_test.py`, `src/avpe/control_http.py`, `src/avpe/input_probe.py`, `src/avpe/memory_card_probe.py` | `main()`, `press_buttons()`, `await_memory_card_ready()` | [control-test contract](re/headless.md) |
| Control-test proof reporting | Shared JSON probe acceptance/error reporting and dispatch-bound menu-pointer proof policy for surfaceless diagnostics | `src/avpe/control_test.py`, `src/avpe/native_menu_pointer_dispatch_probe.py` | `report_json_probe()`, `probe_native_menu_pointer_dispatch()` | [control-test contract](re/headless.md) |
| Pause Quit confirmation discovery | Bounded selected-rectangle inspection, live text/action validation, and dispatch-bound focus proof for the pause-menu Quit confirmation; no BIOS capture policy | `src/avpe/native_pause_quit_probe.py` | `pause_selection_rectangles()`, `focus_pause_selection()` | [BIOS/IOP contract](re/bios.md) |
| Native cache proof policy | Bounded-cache snapshot validation and active-cache polling, independent of process orchestration | `src/avpe/native_asset_cache_probe.py` | `cache_snapshot_is_verified()` | [disc-I/O RE contract](re/disc-io.md) |
| BIOS/IOP trace proof policy | Clean-boot polling, strict bounded/ordered census acceptance, grounded mission-boundary validation, and phase-labelled artifact writing | `src/avpe/native_bios_probe.py` | `bios_trace_is_verified()`, `mission_boundary_is_verified()`, `run_bios_phase()` | [BIOS/IOP contract](re/bios.md) |
| Title-menu lifecycle proof | Restored-title Start transition, live-menu admission, and exact focused physical activation; no profile persistence or BIOS event policy | `src/avpe/native_title_probe.py` | `reach_title_menu()`, `activate_title_menu()` | [BIOS/IOP contract](re/bios.md) |
| BIOS/IOP result-summary validation | Strict scalar encoding, range, extrema, and transition-count acceptance shared by trace event validation | `src/avpe/bios_result.py` | `event_result_is_verified()` | [BIOS/IOP contract](re/bios.md) |
| BIOS/IOP inventory analysis | Deterministic grouping of captured trace events by service and runtime category; no inferred calls | `src/avpe/bios_inventory.py`, `tools/analyze_bios_traces.py` | `summarize_bios_artifact()`, `combine_bios_inventories()` | [BIOS/IOP contract](re/bios.md) |
| Static EE syscall inventory | Bounded executable-segment scan of direct BIOS wrapper callsites and direct syscall instructions; static candidates only | `src/avpe/ee_syscalls.py`, `tools/analyze_ee_syscalls.py` | `scan_ee_syscalls()` | [BIOS/IOP contract](re/bios.md) |
| Static IOP import inventory | Bounded IRX `.iopmod` and import-table scan with library/ordinal identity; static candidates only | `src/avpe/iop_imports.py`, `tools/analyze_iop_modules.py` | `scan_iop_module()` | [BIOS/IOP contract](re/bios.md) |
| Save-format evidence parser | Grounded BWJ decoding and fixed game-save prefix/marker summaries; no native backend ownership | `src/avpe/save_format.py`, `tools/analyze_save_records.py` | `decode_bwj()`, `parse_game_save_record()` | [save-path RE contract](re/save-path.md) |
| Save descriptor evidence parser | Bounded live class-type/descriptor extraction and descriptor-defined wire-body splitting; leaves class-specific `SaveEx` payloads to RE | `src/avpe/save_descriptor_probe.py`, `tools/inspect_save_descriptors.py` | `inspect_class_type_database()`, `parse_serialized_descriptor_body()` | [save-path RE contract](re/save-path.md) |
| SaveEx payload evidence parser | Bounded readers for selected fixed, bitmap, message-queue, and conditional class payloads; no recursive stream ownership | `src/avpe/save_ex.py` | `parse_gunit_payload()`, `parse_gobject_ai_payload_from_database()` | [save-path RE contract](re/save-path.md) |
| Save object-stream evidence parser | Bounded recursive object structures, descriptor bodies, delayed handle-ordered `SaveEx` payloads, and JSON evidence reports; no native backend ownership | `src/avpe/save_stream.py` | `parse_serialized_object_stream()`, `serialize_object_stream()` | [save-path RE contract](re/save-path.md) |
| Save message-type evidence parser | Bounded decoding of the live 256-slot CMessage creator/size table and strict fixed-size lookup | `src/avpe/save_message_types.py`, `tools/inspect_message_types.py` | `parse_message_type_database()`, `fixed_message_size()` | [save-path RE contract](re/save-path.md) |
| Project verification | Python behavior, isolation, dependency, and source-structure regressions | `tests/`, `tools/verify.py` | `tools/verify.py` | — |
| Hosted verification | Asset-free supported-host preparation and normal verification composition; workflow owns only runner/bootstrap selection | `src/avpe/ci.py`, `tools/ci.py`, `.github/workflows/verify.yml` | `verify_host()`, `tools/ci.py` | — |
| Project logging | Single Python log-level gate | `src/avpe/log.py` | `log()` | — |
| Raw-sector conversion | Streaming, validated 2352-byte-sector to ISO block conversion | `src/avpe/raw_sector.py`; CLI in `tools/raw2352.py` | `strip_image()` | — |
| ISO asset extraction | Strict ISO9660 traversal and bounded file extraction | `src/avpe/iso9660.py` | `IsoImage` | [disc-I/O RE contract](re/disc-io.md) |
| Native asset provisioning | CHD extraction, supported-revision anchors, manifest/hash validation, atomic store publication | `src/avpe/native_assets.py` | `provision_native_assets()` | [disc-I/O RE contract](re/disc-io.md) |
| Native asset store admission | Exact launcher-admitted manifest identity, strict manifest-member index, file size/content validation, and generation-safe asset records | `src/avpe/native_assets.py`, `thirdparty/pcsx2/pcsx2/AVPE/NativeAssetStore.*` | `manifest_sha256()`, `AVPE::NativeAssetStore::Resolve()` | [disc-I/O RE contract](re/disc-io.md) |
| Control client | HTTP operations for state, memory, input, and snapshots | `tools/avpe_http.py` | `main()` | [control-channel contract](re/control-channel.md) |
| Control server | Loopback routes and VM/CPU-thread dispatch | `thirdparty/pcsx2/pcsx2/AVPE/AVPE.cpp/.h` | `AVPE::Start()` | [control-channel contract](re/control-channel.md) |
| EE-call execution | Guest-call queue, context, return-PC stop, budget, and result handling | `thirdparty/pcsx2/pcsx2/AVPE/EECallShuttle.cpp/.h` | `AVPE::EECallShuttle` | [input-path contract](re/input-path.md) |
| EE execution observation composition | One narrow interpreter/recompiler dispatch point for AVPE mission timing, BIOS tracing, and demand-driven title yield observers | `thirdparty/pcsx2/pcsx2/AVPE/NativeEeExecutionHooks.cpp/.h`; narrow calls in both EE engines | `AVPE::NativeEeExecutionHooks::Observe()` | [BIOS/IOP contract](re/bios.md) |
| IOP return observation composition | Exact registered caller-return observation for oracle import result pairing; registered blocks only in the recompiler and a pending-call gate in the interpreter | `thirdparty/pcsx2/pcsx2/AVPE/NativeIopExecutionHooks.cpp/.h`; narrow calls in both IOP engines | `AVPE::NativeIopExecutionHooks::ObserveIopExecution()` | [BIOS/IOP contract](re/bios.md) |
| IOP return-site registry | Fixed process-lifetime serialized admission and lock-free exact membership lookup for oracle caller return PCs; no event or import policy | `thirdparty/pcsx2/pcsx2/AVPE/NativeIopReturnSites.cpp/.h` | `AVPE::NativeIopReturnSites::Register()`, `Contains()` | [BIOS/IOP contract](re/bios.md) |
| Native runtime configuration | One immutable, typed AVP:E environment snapshot for diagnostic switches, control-server settings, and native asset admission; product subsystems receive narrow accessors and never read process environment state | `thirdparty/pcsx2/pcsx2/AVPE/NativeConfig.cpp/.h` | `AVPE::NativeConfig` | [control-channel contract](re/control-channel.md) |
| Mission-modal host yield | Demand-driven host CPU message pumping only at the exact AVP:E mission-goals load loop while an EE-call transaction is pending | `thirdparty/pcsx2/pcsx2/AVPE/NativeHostYield.cpp/.h`; frontend pump in `pcsx2-avpe/EmulationThread.*` and `HostServices.cpp` | `AVPE::NativeHostYield::Observe()` | [BIOS/IOP contract](re/bios.md) |
| Shared pointer motion | Normalized-coordinate validation, resolution lookup, bounded guest staging, and absolute game-pointer movement | `thirdparty/pcsx2/pcsx2/AVPE/NativePointerMotion.cpp/.h` | `AVPE::NativePointerMotion::MoveAbsolute()` | [input-path contract](re/input-path.md) |
| Shared native input staging | Little-endian encoding of AVP:E's eight-byte float-pair `CInputData` prefix | `thirdparty/pcsx2/pcsx2/AVPE/NativeInputData.cpp/.h` | `AVPE::NativeInputData::EncodeFloatPair()` | [input-path contract](re/input-path.md) |
| Native gameplay input | Live gameplay-pointer validation, selector policy, selection edges, and contextual commands | `thirdparty/pcsx2/pcsx2/AVPE/NativeInput.cpp/.h` | `AVPE::NativeInput::MoveAbsolute()` | [input-path contract](re/input-path.md) |
| Native camera input | Original camera move/rotate/zoom calls, minimap pointer integration, and before/after state capture | `thirdparty/pcsx2/pcsx2/AVPE/NativeCameraInput.cpp/.h` | `AVPE::NativeCameraInput::Apply()` | [input-path contract](re/input-path.md) |
| Native menu input | Callback-registry menu discovery, synchronous mission-goals modal/Exit discovery, exact focus and text-pointer observation, hit-testing, activation/cancel actions, and bounded exact-state physical-pad admission | `thirdparty/pcsx2/pcsx2/AVPE/NativeMenuInput.cpp/.h` | `AVPE::NativeMenuInput` | [input-path contract](re/input-path.md) |
| Native menu control route | Diagnostic HTTP parsing, failure/status mapping, and JSON presentation for typed menu state/actions and readiness requests | `thirdparty/pcsx2/pcsx2/AVPE/NativeMenuRoute.cpp/.h` | `AVPE::NativeMenuRoute::HandleAction()`, `HandleState()`, `HandleReadiness()` | [control-channel contract](re/control-channel.md) |
| Guest pad readiness | Read-only validated CPS2Input owner, port, initialization flags, libpad state, and current/previous reports; no input or menu mutation | `thirdparty/pcsx2/pcsx2/AVPE/NativePadReadiness.cpp/.h` | `AVPE::NativePadReadiness::IsReady()` | [input-path contract](re/input-path.md) |
| Normal input-dispatch observer | Live `GInputDevice` registry admission, current `GAttractExit`-owner state, callback identities, owner-vtable evidence, and exact queued pointer/menu callback replacement at the shipping dispatch boundary; no title-lifecycle action policy | `thirdparty/pcsx2/pcsx2/AVPE/NativeInputDispatch.cpp/.h` | `AVPE::NativeInputDispatch` | [input-path contract](re/input-path.md) |
| Title-transition observer | Passive, exact-PC recording of the validated `GPressStartMenu::ItemActivated` and dynamic `GProfileMenu::Create` entry order; no input, guest-memory, or profile-storage mutation | `thirdparty/pcsx2/pcsx2/AVPE/NativeTitleTransition.cpp/.h`, composed by `NativeEeExecutionHooks.*` | `AVPE::NativeTitleTransition::{Start,SnapshotJson}` | [BIOS/IOP contract](re/bios.md) |
| Title-transition control route | Diagnostic HTTP parsing, status mapping, and JSON presentation for title-to-profile transition observation; no observer policy | `thirdparty/pcsx2/pcsx2/AVPE/NativeTitleTransitionRoute.cpp/.h` | `AVPE::NativeTitleTransitionRoute::{Start,Snapshot}` | [control-channel contract](re/control-channel.md) |
| Memory-card readiness observation | CPU-thread slot presence, savestate auto-eject countdown, busy state, and derived readiness; no card policy or mutation | `thirdparty/pcsx2/pcsx2/AVPE/NativeMemoryCardState.cpp/.h` | `AVPE::NativeMemoryCardState::Capture()` | [control-channel contract](re/control-channel.md) |
| Grounded BIOS-boundary control routes | HTTP status mapping and CPU-thread handoff for the game-load, game-save, and shell-shutdown census boundaries; no capture semantics or menu policy | `thirdparty/pcsx2/pcsx2/AVPE/NativeBiosBoundaryRoute.cpp/.h` | `AVPE::NativeBiosBoundaryRoute::{Start,Capture}*()` | [BIOS/IOP contract](re/bios.md) |
| Native save bridge | AVP:E save-boundary interception, schema translation, atomic host persistence, and one-time card import | target: a `NativeSaves` peer module under `thirdparty/pcsx2/pcsx2/AVPE/` | target: `AVPE::NativeSaves` | target: save-path RE contract |
| Native asset I/O | AVP:E title gating, path normalization, store/cache lifecycle composition, and FSSOUND cdvdman sector mapping over admitted records | `thirdparty/pcsx2/pcsx2/AVPE/NativeAssets.*`; narrow ioman/cdvdman hooks in `IopBios.cpp` | `AVPE::NativeAssets::ResolveIomanOpen()`, `ResolveCdvdSearch()` | [disc-I/O RE contract](re/disc-io.md) |
| Native asset byte cache | Immutable 64 KiB pages, exact 512-page/32 MiB true-LRU bound, coalesced transient host reads, and generation invalidation shared by ioman and cdvdman | `thirdparty/pcsx2/pcsx2/AVPE/NativeAssetCache.*` | `AVPE::NativeAssetCache::ReadAt()` | [disc-I/O RE contract](re/disc-io.md) |
| Native ioman file adapter | Per-descriptor read/seek cursor over admitted records and the shared cache, with no persistent host file handle | `thirdparty/pcsx2/pcsx2/AVPE/NativeAssetFile.*` | `AVPE::NativeAssetFile::Open()` | [disc-I/O RE contract](re/disc-io.md) |
| Native CDVD completion pairing | Fixed-capacity, one-shot caller-stack pairing from claimed FSSOUND sector reads to their matching `sceCdGetError` result | `thirdparty/pcsx2/pcsx2/AVPE/NativeCdvdCompletion.*`; narrow import hooks in `IopBios.cpp` | `AVPE::NativeCdvdCompletion::Record()`, `Consume()` | [disc-I/O RE contract](re/disc-io.md) |
| Native asset save-state recovery evidence | Atomic CPU-thread descriptor/mapping snapshots and strict live round-trip proof policy over the shipping HLE save-state owner | `thirdparty/pcsx2/pcsx2/AVPE/NativeAssetStateSnapshot.*`, narrow descriptor enumeration in `IopBios.*`, `src/avpe/native_asset_probe.py` | `AVPE::NativeAssetStateSnapshot::CaptureJsonOnCPUThread()`, `probe_native_ioman_state_recovery()`, `probe_native_cdvd_state_recovery()` | [disc-I/O RE contract](re/disc-io.md) |
| Native guest reset evidence | CPU-thread reset boundary, production guest-reset epoch, cleanup attestation, and post-reset native-read proof policy | `thirdparty/pcsx2/pcsx2/AVPE/NativeGuestReset.*`, `R3000A.cpp`, `NativeAssetStateSnapshot.*`, `src/avpe/native_asset_probe.py` | `AVPE::NativeGuestReset::Handle()`, `AVPE::NativeAssets::RecordGuestReset()`, `probe_native_asset_guest_reset()` | [disc-I/O RE contract](re/disc-io.md) |
| Native asset byte differential | Bounded canonical-chunk assembly, PCSX2 ISO-reader oracle capture, strict source-separated comparison, and mismatch controls | `thirdparty/pcsx2/pcsx2/AVPE/NativeAssetByteTrace.*`, `src/avpe/asset_byte_compare.py`, `tools/compare_native_asset_bytes.py` | `AVPE::NativeAssetByteTrace::CaptureIsoOracle()`, `compare_asset_byte_traces()` | [disc-I/O RE contract](re/disc-io.md) |
| Native load timing differential | Grounded guest/host boundary capture, actual-backend identity, strict symmetric sample validation, alternating-run orchestration, and drift/reduction controls | `thirdparty/pcsx2/pcsx2/AVPE/NativeLoadTiming.*`, `src/avpe/load_timing.py`, `tools/compare_native_load_timing.py` | `AVPE::NativeLoadTiming::SnapshotJson()`, `compare_load_timing_samples()` | [disc-I/O RE contract](re/disc-io.md) |
| BIOS/IOP observation census | Trace lifecycle plus grounded mission entry/return, loader/chunk timing, nested `LoadCore` phases, indirect initializers, and object factories; no service behavior ownership | `thirdparty/pcsx2/pcsx2/AVPE/NativeBiosTrace.*`, `NativeMissionLoadTiming.*`, narrow calls in `IopBios.cpp` | `AVPE::NativeBiosTrace::SnapshotJson()`, `CaptureMissionBoundaryJson()` | [BIOS/IOP contract](re/bios.md) |
| Game-save census boundary | Exact `CProfile::SaveGame` profile-validated entry and final-return observation, including BIOS/IOP capture scoping and returned game result; no input policy or native-save implementation | `thirdparty/pcsx2/pcsx2/AVPE/NativeGameSaveBoundary.*`; composed by `NativeEeExecutionHooks.*` | `AVPE::NativeGameSaveBoundary::Start()`, `CaptureJson()` | [BIOS/IOP contract](re/bios.md) |
| Game-load census boundary | Exact `CProfile::LoadGame` profile-validated entry and final-return observation after live `GLoadPacifyMenu::Process`, plus the surfaceless normal-menu and synchronous mission-modal proof policy; no native-save implementation | `thirdparty/pcsx2/pcsx2/AVPE/NativeGameLoadBoundary.*`, composed by `NativeEeExecutionHooks.*`; `src/avpe/native_game_load_probe.py` | `AVPE::NativeGameLoadBoundary::Start()`, `CaptureJson()`; `run_game_load_phase()` | [BIOS/IOP contract](re/bios.md) |
| Shell-shutdown census boundary | Exact live `CShell::Quit` entry through `CShell::MainLoop` return, including BIOS/IOP capture scoping and quit-bit validation; no menu policy or host/VM lifecycle ownership | `thirdparty/pcsx2/pcsx2/AVPE/NativeShellShutdownBoundary.*`; composed by `NativeEeExecutionHooks.*` | `AVPE::NativeShellShutdownBoundary::Start()`, `CaptureJson()` | [BIOS/IOP contract](re/bios.md) |
| BIOS/IOP census event store | Bounded sequence-ordered event admission, identity/result-summary coalescing, JSON serialization, and exact EE BIOS and IOP oracle entry/return pairing under the trace owner's lock | `thirdparty/pcsx2/pcsx2/AVPE/NativeBiosEventStore.*` | `AVPE::NativeBiosEventStore::Store` | [BIOS/IOP contract](re/bios.md) |
| AVP:E-specific HLE BIOS | Required firmware-service inventory, clean-room EE kernel/BIOS behavior, IOP/module services, and BIOS-free boot policy | target: a dedicated `HLE` submodule under `thirdparty/pcsx2/pcsx2/AVPE/`; narrow hooks at existing BIOS/IOP service owners | target: `AVPE::HLE` | target: HLE-BIOS RE contract |
| Native options integration | AVP:E menu extension and game-facing bindings to host display/graphics settings | target: `thirdparty/pcsx2/pcsx2/AVPE/NativeOptions.*`; narrow settings interface in `thirdparty/pcsx2/pcsx2-avpe/` | target: `AVPE::NativeOptions` | target: native-options contract |
| Diagnostic UI | RmlUi developer-only diagnostics and inspection surfaces | target: a `DebugUI` module under `thirdparty/pcsx2/pcsx2-avpe/` | target: `AVPE::DebugUI` | target: debug-UI contract |
| Diagnostic pad injection | Bootstrap-only active-low DS2 injection | `thirdparty/pcsx2/pcsx2/SIO/Pad/PadDualshock2.cpp` | `GetButtons()` integration | [control-channel contract](re/control-channel.md) |
| RE helpers | Ghidra extraction, caller discovery, static-data inspection, singleton inventory | `tools/ghidra_scripts/`, `tools/pthe_syms.txt` | individual tools | [input-path contract](re/input-path.md) |
| Evidence | Falsifiable claims and verification dependencies | `docs/info/claims/` | claim files | — |

## Source map

```text
run.sh                         locked launcher shim
src/avpe/                      host-side product orchestration
├── cli.py                     command and prerequisite owner
├── ci.py                      hosted asset-free verification composition
├── control_http.py            isolated loopback control transport
├── dependencies.py            submodule inspection/provisioning owner
├── iso9660.py                 strict user-disc filesystem reader
├── launch.py                  emulator process/config owner
├── log.py                     Python logging owner
├── native_assets.py           validated native-store provisioner
├── native_asset_cache_probe.py bounded-cache proof policy
├── native_asset_probe.py       native lifecycle and live save/load proof policy
├── native_bios_probe.py        clean-boot BIOS/IOP trace proof policy
├── native_title_probe.py       title-menu lifecycle and physical activation proof
├── native_game_load_probe.py   normal game-load flow and boundary proof policy
├── bios_result.py              strict bounded service-result validation
├── input_probe.py              observed diagnostic pad press/release lifecycle
├── memory_card_probe.py        isolated card copy and live readiness proof policy
├── native_menu_pointer_dispatch_probe.py dispatch-bound menu pointer proof policy
├── native_pause_quit_probe.py  grounded pause Quit confirmation discovery
├── bios_inventory.py           deterministic BIOS/IOP trace summaries
├── iop_imports.py              static IRX IOP import-table parser
├── save_format.py              grounded BWJ/save-prefix parser
├── asset_byte_compare.py      strict native/ISO chunk comparator
├── load_timing.py             strict symmetric timing comparison policy
└── raw_sector.py              streaming raw-sector converter
tools/                         project automation and control clients
├── avpe_http.py               live control client
├── run_control_test.py        surfaceless and silent test process owner
├── compare_native_asset_bytes.py  byte differential and OTHER-answer control
├── compare_native_load_timing.py  alternating timing differential and controls
├── analyze_bios_traces.py       captured BIOS/IOP inventory report
├── analyze_iop_modules.py       static IRX IOP import inventory
├── analyze_save_records.py      extracted game-save record report
├── raw2352.py                 disc-sector conversion
└── ghidra_scripts/            maintainer-only RE extraction
thirdparty/pcsx2/pcsx2/AVPE/   fork-side AVPE integration owner
├── GuestObjects.*             validated AVP:E guest object/handle reads
├── NativeConfig.*             immutable typed runtime configuration owner
├── NativeAssets.*             title-gated ioman/CDVD native asset boundary and observations
├── NativeAssetByteTrace.*     bounded native/ISO canonical-chunk evidence
├── NativeAssetCache.*         bounded immutable-page LRU and transient host reads
├── NativeCdvdCompletion.*     one-shot native read/GetError result pairing
├── NativeAssetFile.*          cache-backed ioman descriptor cursor
├── NativeAssetStore.*         exact manifest admission and validated member index
├── NativeAssetStateSnapshot.* atomic diagnostic view of frozen native I/O state
├── NativeLoadTiming.*         grounded native/optical loading-time evidence
├── NativeBiosEventStore.*     bounded BIOS/IOP events and exact return pairing
├── NativeBiosBoundaryRoute.*  grounded game-load/save/shutdown control routes
├── NativeBiosTrace.*          trace lifecycle and grounded mission load progress/boundary capture
├── NativeGameSaveBoundary.*   exact CProfile::SaveGame capture boundary
├── NativeGameLoadBoundary.*   exact CProfile::LoadGame capture boundary
├── NativeShellShutdownBoundary.* exact CShell::Quit to MainLoop-return capture boundary
├── NativeEeExecutionHooks.*   shared EE observer composition point
├── NativeIopExecutionHooks.*  exact registered IOP return observation point
├── NativeIopReturnSites.*     bounded exact IOP caller-return PC registry
├── NativeHostYield.*          exact mission-modal host CPU transaction yield
├── NativeInput.*              gameplay pointer and button semantics
├── NativeInputDispatch.*      normal callback-dispatch observation and queued actions
├── NativeTitleTransition.*    passive title-to-profile handoff observation
├── NativeTitleTransitionRoute.* HTTP adapter for title-transition evidence
├── NativeMemoryCardState.*    CPU-thread card readiness observation
├── NativePadReadiness.*       guest controller initialization/report readiness
├── NativeMenuInput.*          callback/menu-modal discovery and typed menu actions
├── NativeMenuRoute.*          native-menu diagnostic HTTP adapter
└── NativePointerMotion.*      shared absolute pointer movement mechanics
thirdparty/pcsx2/pcsx2-avpe/    standalone product frontend
├── Main.cpp                    process composition and product CLI
├── Runtime.*                   host-facing frontend orchestration
├── EmulationThread.*           PCSX2 core lifecycle owner
├── HostServices.cpp            PCSX2 Host callback implementation
├── HostInputRouter.*          key/mouse-to-typed-action policy
├── HostWindow.*               window and platform event capture
└── RenderSurface.*            low-level native graphics surface
docs/re/                       subsystem RE and operating contracts
docs/info/claims/              evidence ledger
docs/issues/                   atomic work and investigation points
```

## Where does new work go?

- Guest function invocation and EE register/PC lifetime belong in the dedicated
  fork-local `EECallShuttle` module, not the HTTP route implementation.
- EE instruction observation composition belongs in `NativeEeExecutionHooks`;
  exact title wait-loop host pumping belongs in `NativeHostYield`. Neither owns
  guest menu semantics or grows the interpreter/recompiler entry points.
- Gameplay keyboard/mouse semantics belong in fork-local `NativeInput`; menu
  discovery and actions belong in peer `NativeMenuInput`. Shared absolute
  pointer mechanics belong in `NativePointerMotion`; both semantic owners use
  validated object and handle reads through `GuestObjects`. Host clients only
  translate platform events into typed intent.
- AVP:E save interception, schema translation, atomic files, and memory-card
  import belong in the dedicated fork-local `NativeSaves` module; generic PCSX2
  card emulation remains outside that owner.
- AVP:E namespace, guest-visible asset semantics, and lifecycle composition
  belong in fork-local `NativeAssets`; exact manifest admission, member lookup,
  and content identity belong in its private `NativeAssetStore` peer. Bounded
  immutable pages and transient host reads belong in `NativeAssetCache`, while
  `NativeAssetFile` owns only the ioman descriptor cursor. Both ioman and
  cdvdman consume the same generation-safe cache through `NativeAssets`.
  The matching FSSOUND `sceCdGetError` result belongs in the bounded
  `NativeCdvdCompletion` peer rather than consulting unrelated optical state.
  Grounded CDVD/IOP hooks call that owner; they do not absorb game-specific
  file tables or host I/O policy.
- Native-versus-ISO byte evidence belongs in the peer `NativeAssetByteTrace`
  module and the strict Python comparator. It does not own shipping I/O policy
  and must stay disabled during loading-time measurements.
- Native-versus-optical timing evidence belongs in peer `NativeLoadTiming`,
  the strict Python timing policy, and the sequential comparison tool. It does
  not own shipping cache policy, and it never runs with byte tracing enabled.
- AVP:E-specific firmware behavior belongs in a dedicated HLE submodule under
  the fork-local `thirdparty/pcsx2/pcsx2/AVPE/`
  owner. Existing BIOS, EE kernel, and IOP integration points remain narrow
  hooks; they do not become a second copy of the game-specific service model.
- The visible native window and its platform lifecycle belong in the fork's
  standalone `thirdparty/pcsx2/pcsx2-avpe/` frontend. PCSX2's Qt application
  is a diagnostic/oracle frontend only and is absent from the product target.
- Desktop options are presented by AVP:E's existing menu system through a
  dedicated `NativeOptions` owner. It calls a narrow frontend interface whose
  standalone implementation delegates to the existing PCSX2 graphics/display
  setting owners; the guest menu does not own host persistence policy.
- Optional RmlUi diagnostics belong in a dedicated `DebugUI/` frontend module.
  They may inspect the same narrow interfaces but do not become the shipping
  options surface or a second source of settings policy.
- New HTTP framing/server capability belongs in Lucent; AVPE owns only routes
  and game-specific semantics.
- New launcher commands compose modules under `src/avpe/`; discovery, build,
  and launch policy do not grow in `run.sh`.
- Reverse-engineered facts go in the relevant `docs/re/` contract and claims;
  goals, project state, and issues retain their separate authorities.
