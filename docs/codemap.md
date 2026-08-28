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
| Dependency-prefix provisioning | Selects and invokes the tracked PCSX2 Qt/dependency workflow in `scratch/`, with tool checks and post-build prefix validation | `src/avpe/dependency_prefix.py`, `thirdparty/pcsx2/.github/workflows/scripts/` | `provision_dependency_prefix()` | — |
| Product launch | Native-store validation, AVPE host argv/environment, product config, process lifetime | `src/avpe/launch.py` | `launch()` | — |
| Standalone frontend runtime | Product process composition, PCSX2 core thread/lifecycle, and host callbacks | `thirdparty/pcsx2/pcsx2-avpe/Runtime.*`, `EmulationThread.*`, `HostServices.cpp`, `Main.cpp` | `avpe` executable | [presentation](host/presentation.md) |
| Native host shell | Sole visible top-level window, render-surface lifecycle, resize/fullscreen, focus, product shutdown | `thirdparty/pcsx2/pcsx2-avpe/HostWindow.*`, `RenderSurface.*`, `NativeWindow.*` | `AVPE::HostWindow` | [presentation](host/presentation.md) |
| Product input routing | Qt key and mouse translation, held-input ownership across menu/game transitions, and typed action dispatch | `thirdparty/pcsx2/pcsx2-avpe/HostInputRouter.*` | `AVPE::HostInputRouter` | [input path](re/input-path.md) |
| Presentation bridge | GS-to-host window acquisition and narrow display/settings control | `thirdparty/pcsx2/pcsx2-avpe/HostServices.cpp`, `Runtime.*` | `Host::AcquireRenderWindow()` | [presentation](host/presentation.md) |
| Control-test runner | Silent surfaceless PCSX2 process, isolated profile/card working copies, loopback transport, timebox, exact process-group cleanup | `tools/run_control_test.py`, `src/avpe/control_http.py`, `src/avpe/memory_card_probe.py` | `main()` | [control-test contract](re/headless.md) |
| Native cache proof policy | Bounded-cache snapshot validation and active-cache polling, independent of process orchestration | `src/avpe/native_asset_cache_probe.py` | `cache_snapshot_is_verified()` | [disc-I/O RE contract](re/disc-io.md) |
| Project verification | Python behavior, isolation, dependency, and source-structure regressions | `tests/`, `tools/verify.py` | `tools/verify.py` | — |
| Project logging | Single Python log-level gate | `src/avpe/log.py` | `log()` | — |
| Raw-sector conversion | Streaming, validated 2352-byte-sector to ISO block conversion | `src/avpe/raw_sector.py`; CLI in `tools/raw2352.py` | `strip_image()` | — |
| ISO asset extraction | Strict ISO9660 traversal and bounded file extraction | `src/avpe/iso9660.py` | `IsoImage` | [disc-I/O RE contract](re/disc-io.md) |
| Native asset provisioning | CHD extraction, supported-revision anchors, manifest/hash validation, atomic store publication | `src/avpe/native_assets.py` | `provision_native_assets()` | [disc-I/O RE contract](re/disc-io.md) |
| Native asset store admission | Exact launcher-admitted manifest identity, strict manifest-member index, file size/content validation, and generation-safe asset records | `src/avpe/native_assets.py`, `thirdparty/pcsx2/pcsx2/AVPE/NativeAssetStore.*` | `manifest_sha256()`, `AVPE::NativeAssetStore::Resolve()` | [disc-I/O RE contract](re/disc-io.md) |
| Control client | HTTP operations for state, memory, input, and snapshots | `tools/avpe_http.py` | `main()` | [control-channel contract](re/control-channel.md) |
| Control server | Loopback routes and VM/CPU-thread dispatch | `thirdparty/pcsx2/pcsx2/AVPE/AVPE.cpp/.h` | `AVPE::Start()` | [control-channel contract](re/control-channel.md) |
| EE-call execution | Guest-call queue, context, return-PC stop, budget, and result handling | `thirdparty/pcsx2/pcsx2/AVPE/EECallShuttle.cpp/.h` | `AVPE::EECallShuttle` | [input-path contract](re/input-path.md) |
| Shared pointer motion | Normalized-coordinate validation, resolution lookup, bounded guest staging, and absolute game-pointer movement | `thirdparty/pcsx2/pcsx2/AVPE/NativePointerMotion.cpp/.h` | `AVPE::NativePointerMotion::MoveAbsolute()` | [input-path contract](re/input-path.md) |
| Native gameplay input | Live gameplay-pointer validation, selector policy, selection edges, and contextual commands | `thirdparty/pcsx2/pcsx2/AVPE/NativeInput.cpp/.h` | `AVPE::NativeInput::MoveAbsolute()` | [input-path contract](re/input-path.md) |
| Native menu input | Active menu and menu-capable pointer discovery, focus navigation, hit-testing, and activation/cancel actions | `thirdparty/pcsx2/pcsx2/AVPE/NativeMenuInput.cpp/.h` | `AVPE::NativeMenuInput` | [input-path contract](re/input-path.md) |
| Native save bridge | AVP:E save-boundary interception, schema translation, atomic host persistence, and one-time card import | target: a `NativeSaves` peer module under `thirdparty/pcsx2/pcsx2/AVPE/` | target: `AVPE::NativeSaves` | target: save-path RE contract |
| Native asset I/O | AVP:E title gating, path normalization, store/cache lifecycle composition, and FSSOUND cdvdman sector mapping over admitted records | `thirdparty/pcsx2/pcsx2/AVPE/NativeAssets.*`; narrow ioman/cdvdman hooks in `IopBios.cpp` | `AVPE::NativeAssets::ResolveIomanOpen()`, `ResolveCdvdSearch()` | [disc-I/O RE contract](re/disc-io.md) |
| Native asset byte cache | Immutable 64 KiB pages, exact 512-page/32 MiB true-LRU bound, coalesced transient host reads, and generation invalidation shared by ioman and cdvdman | `thirdparty/pcsx2/pcsx2/AVPE/NativeAssetCache.*` | `AVPE::NativeAssetCache::ReadAt()` | [disc-I/O RE contract](re/disc-io.md) |
| Native ioman file adapter | Per-descriptor read/seek cursor over admitted records and the shared cache, with no persistent host file handle | `thirdparty/pcsx2/pcsx2/AVPE/NativeAssetFile.*` | `AVPE::NativeAssetFile::Open()` | [disc-I/O RE contract](re/disc-io.md) |
| Native CDVD completion pairing | Fixed-capacity, one-shot caller-stack pairing from claimed FSSOUND sector reads to their matching `sceCdGetError` result | `thirdparty/pcsx2/pcsx2/AVPE/NativeCdvdCompletion.*`; narrow import hooks in `IopBios.cpp` | `AVPE::NativeCdvdCompletion::Record()`, `Consume()` | [disc-I/O RE contract](re/disc-io.md) |
| Native asset save-state recovery evidence | Atomic CPU-thread descriptor/mapping snapshots and strict live round-trip proof policy over the shipping HLE save-state owner | `thirdparty/pcsx2/pcsx2/AVPE/NativeAssetStateSnapshot.*`, narrow descriptor enumeration in `IopBios.*`, `src/avpe/native_asset_probe.py` | `AVPE::NativeAssetStateSnapshot::CaptureJsonOnCPUThread()`, `probe_native_ioman_state_recovery()`, `probe_native_cdvd_state_recovery()` | [disc-I/O RE contract](re/disc-io.md) |
| Native guest reset evidence | CPU-thread reset boundary, production guest-reset epoch, cleanup attestation, and post-reset native-read proof policy | `thirdparty/pcsx2/pcsx2/AVPE/NativeGuestReset.*`, `R3000A.cpp`, `NativeAssetStateSnapshot.*`, `src/avpe/native_asset_probe.py` | `AVPE::NativeGuestReset::Handle()`, `AVPE::NativeAssets::RecordGuestReset()`, `probe_native_asset_guest_reset()` | [disc-I/O RE contract](re/disc-io.md) |
| Native asset byte differential | Bounded canonical-chunk assembly, PCSX2 ISO-reader oracle capture, strict source-separated comparison, and mismatch controls | `thirdparty/pcsx2/pcsx2/AVPE/NativeAssetByteTrace.*`, `src/avpe/asset_byte_compare.py`, `tools/compare_native_asset_bytes.py` | `AVPE::NativeAssetByteTrace::CaptureIsoOracle()`, `compare_asset_byte_traces()` | [disc-I/O RE contract](re/disc-io.md) |
| Native load timing differential | Grounded guest/host boundary capture, actual-backend identity, strict symmetric sample validation, alternating-run orchestration, and drift/reduction controls | `thirdparty/pcsx2/pcsx2/AVPE/NativeLoadTiming.*`, `src/avpe/load_timing.py`, `tools/compare_native_load_timing.py` | `AVPE::NativeLoadTiming::SnapshotJson()`, `compare_load_timing_samples()` | [disc-I/O RE contract](re/disc-io.md) |
| AVP:E-specific HLE BIOS | Required firmware-service inventory, clean-room EE kernel/BIOS behavior, IOP/module services, and BIOS-free boot policy | target: a dedicated `HLE` submodule under `thirdparty/pcsx2/pcsx2/AVPE/`; narrow hooks at existing BIOS/IOP service owners | target: `AVPE::HLE` | target: HLE-BIOS RE contract |
| Native options integration | AVP:E menu extension and game-facing bindings to host display/graphics settings | target: `thirdparty/pcsx2/pcsx2/AVPE/NativeOptions.*`; narrow settings interface in `thirdparty/pcsx2/pcsx2-avpe/` | target: `AVPE::NativeOptions` | target: native-options contract |
| Diagnostic UI | RmlUi developer-only diagnostics and inspection surfaces | target: a `DebugUI` module under `thirdparty/pcsx2/pcsx2-avpe/` | target: `AVPE::DebugUI` | target: debug-UI contract |
| Diagnostic pad injection | Bootstrap-only active-low DS2 injection | `thirdparty/pcsx2/pcsx2/SIO/Pad/PadDualshock2.cpp` | `GetButtons()` integration | [control-channel contract](re/control-channel.md) |
| RE helpers | Ghidra extraction, caller discovery, singleton inventory | `tools/ghidra_scripts/`, `tools/pthe_syms.txt` | individual tools | [input-path contract](re/input-path.md) |
| Evidence | Falsifiable claims and verification dependencies | `docs/info/claims/` | claim files | — |

## Source map

```text
run.sh                         locked launcher shim
src/avpe/                      host-side product orchestration
├── cli.py                     command and prerequisite owner
├── control_http.py            isolated loopback control transport
├── dependencies.py            submodule inspection/provisioning owner
├── iso9660.py                 strict user-disc filesystem reader
├── launch.py                  emulator process/config owner
├── log.py                     Python logging owner
├── native_assets.py           validated native-store provisioner
├── native_asset_cache_probe.py bounded-cache proof policy
├── native_asset_probe.py       native lifecycle and live save/load proof policy
├── asset_byte_compare.py      strict native/ISO chunk comparator
├── load_timing.py             strict symmetric timing comparison policy
└── raw_sector.py              streaming raw-sector converter
tools/                         project automation and control clients
├── avpe_http.py               live control client
├── run_control_test.py        surfaceless and silent test process owner
├── compare_native_asset_bytes.py  byte differential and OTHER-answer control
├── compare_native_load_timing.py  alternating timing differential and controls
├── raw2352.py                 disc-sector conversion
└── ghidra_scripts/            maintainer-only RE extraction
thirdparty/pcsx2/pcsx2/AVPE/   fork-side AVPE integration owner
├── GuestObjects.*             validated AVP:E guest object/handle reads
├── NativeAssets.*             title-gated ioman/CDVD native asset boundary and observations
├── NativeAssetByteTrace.*     bounded native/ISO canonical-chunk evidence
├── NativeAssetCache.*         bounded immutable-page LRU and transient host reads
├── NativeCdvdCompletion.*     one-shot native read/GetError result pairing
├── NativeAssetFile.*          cache-backed ioman descriptor cursor
├── NativeAssetStore.*         exact manifest admission and validated member index
├── NativeAssetStateSnapshot.* atomic diagnostic view of frozen native I/O state
├── NativeLoadTiming.*         grounded native/optical loading-time evidence
├── NativeInput.*              gameplay pointer and button semantics
├── NativeMenuInput.*          active-menu discovery and typed menu actions
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
