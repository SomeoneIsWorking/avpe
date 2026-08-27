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
| Dependency provisioning | PCSX2 gitlink inspection plus recursive submodule initialization; dependency provenance | `src/avpe/dependencies.py`, `.gitmodules`, `deps.toml` | `provision_submodules()` | — |
| Product launch | AVPE host argv, product config, process lifetime | `src/avpe/launch.py` | `launch()` | — |
| Standalone frontend runtime | Product process composition, PCSX2 core thread/lifecycle, and host callbacks | `thirdparty/pcsx2/pcsx2-avpe/Runtime.*`, `EmulationThread.*`, `HostServices.cpp`, `Main.cpp` | `avpe` executable | [presentation](host/presentation.md) |
| Native host shell | Sole visible top-level window, render-surface lifecycle, resize/fullscreen, focus, product shutdown | `thirdparty/pcsx2/pcsx2-avpe/HostWindow.*`, `RenderSurface.*`, `NativeWindow.*` | `AVPE::HostWindow` | [presentation](host/presentation.md) |
| Product input routing | Qt key and mouse translation, held-input ownership across menu/game transitions, and typed action dispatch | `thirdparty/pcsx2/pcsx2-avpe/HostInputRouter.*` | `AVPE::HostInputRouter` | [input path](re/input-path.md) |
| Presentation bridge | GS-to-host window acquisition now; future same-frame RmlUi composition and narrow display/settings control | `thirdparty/pcsx2/pcsx2-avpe/HostServices.cpp`, `Runtime.*` | `Host::AcquireRenderWindow()` | [presentation](host/presentation.md) |
| Control-test runner | Silent surfaceless PCSX2 process, isolated profile, timebox, exact process-group cleanup | `tools/run_control_test.py` | `main()` | [control-test contract](re/headless.md) |
| Project verification | Python behavior, isolation, dependency, and source-structure regressions | `tests/`, `tools/verify.py` | `tools/verify.py` | — |
| Project logging | Single Python log-level gate | `src/avpe/log.py` | `log()` | — |
| Disc conversion | Strict MODE2/2352 to ISO9660 conversion | `tools/raw2352.py` | `main()` | — |
| Control client | HTTP operations for state, memory, input, and snapshots | `tools/avpe_http.py` | `main()` | [control-channel contract](re/control-channel.md) |
| Control server | Loopback routes and VM/CPU-thread dispatch | `thirdparty/pcsx2/pcsx2/AVPE/AVPE.cpp/.h` | `AVPE::Start()` | [control-channel contract](re/control-channel.md) |
| EE-call execution | Guest-call queue, context, return-PC stop, budget, and result handling | `thirdparty/pcsx2/pcsx2/AVPE/EECallShuttle.cpp/.h` | `AVPE::EECallShuttle` | [input-path contract](re/input-path.md) |
| Shared pointer motion | Normalized-coordinate validation, resolution lookup, bounded guest staging, and absolute game-pointer movement | `thirdparty/pcsx2/pcsx2/AVPE/NativePointerMotion.cpp/.h` | `AVPE::NativePointerMotion::MoveAbsolute()` | [input-path contract](re/input-path.md) |
| Native gameplay input | Live gameplay-pointer validation, selector policy, selection edges, and contextual commands | `thirdparty/pcsx2/pcsx2/AVPE/NativeInput.cpp/.h` | `AVPE::NativeInput::MoveAbsolute()` | [input-path contract](re/input-path.md) |
| Native menu input | Active menu and menu-capable pointer discovery, focus navigation, hit-testing, and activation/cancel actions | `thirdparty/pcsx2/pcsx2/AVPE/NativeMenuInput.cpp/.h` | `AVPE::NativeMenuInput` | [input-path contract](re/input-path.md) |
| Native save bridge | AVP:E save-boundary interception, schema translation, atomic host persistence, and one-time card import | target: a `NativeSaves` peer module under `thirdparty/pcsx2/pcsx2/AVPE/` | target: `AVPE::NativeSaves` | target: save-path RE contract |
| Native asset I/O | AVP:E file/sector mapping, validated disc-derived asset store, asynchronous host reads, cache, and optical-path bypass | target: a `NativeAssets` peer module under `thirdparty/pcsx2/pcsx2/AVPE/`; narrow hooks in the grounded CDVD/IOP boundary | target: `AVPE::NativeAssets` | target: disc-I/O RE contract |
| AVP:E-specific HLE BIOS | Required firmware-service inventory, clean-room EE kernel/BIOS behavior, IOP/module services, and BIOS-free boot policy | target: a dedicated `HLE` submodule under `thirdparty/pcsx2/pcsx2/AVPE/`; narrow hooks at existing BIOS/IOP service owners | target: `AVPE::HLE` | target: HLE-BIOS RE contract |
| Native options UI | RmlUi lifecycle, options documents, and game-facing settings bindings | target: `thirdparty/pcsx2/pcsx2-avpe/UI/` | target: `AVPE::NativeSettingsUI` | target: native-options UI contract |
| Diagnostic pad injection | Bootstrap-only active-low DS2 injection | `thirdparty/pcsx2/pcsx2/SIO/Pad/PadDualshock2.cpp` | `GetButtons()` integration | [control-channel contract](re/control-channel.md) |
| RE helpers | Ghidra extraction, caller discovery, singleton inventory | `tools/ghidra_scripts/`, `tools/pthe_syms.txt` | individual tools | [input-path contract](re/input-path.md) |
| Evidence | Falsifiable claims and verification dependencies | `docs/info/claims/` | claim files | — |

## Source map

```text
run.sh                         locked launcher shim
src/avpe/                      host-side product orchestration
├── cli.py                     command and prerequisite owner
├── dependencies.py            submodule inspection/provisioning owner
├── launch.py                  emulator process/config owner
└── log.py                     Python logging owner
tools/                         project automation and control clients
├── avpe_http.py               live control client
├── run_control_test.py        surfaceless and silent test process owner
├── raw2352.py                 disc-sector conversion
└── ghidra_scripts/            maintainer-only RE extraction
thirdparty/pcsx2/pcsx2/AVPE/   fork-side AVPE integration owner
├── GuestObjects.*             validated AVP:E guest object/handle reads
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
- AVP:E asset resolution, native storage, async reads, and caching belong in
  the fork-local `NativeAssets` module. Grounded CDVD/IOP hooks call that owner;
  they do not absorb game-specific file tables or host I/O policy.
- AVP:E-specific firmware behavior belongs in a dedicated HLE submodule under
  the fork-local `thirdparty/pcsx2/pcsx2/AVPE/`
  owner. Existing BIOS, EE kernel, and IOP integration points remain narrow
  hooks; they do not become a second copy of the game-specific service model.
- The visible native window and its platform lifecycle belong in the fork's
  standalone `thirdparty/pcsx2/pcsx2-avpe/` frontend. PCSX2's Qt application
  is a diagnostic/oracle frontend only and is absent from the product target.
- RmlUi documents and input routing belong in a dedicated `UI/` submodule of
  `pcsx2-avpe`; they compose with the product surface and call narrow existing
  PCSX2 graphics/display setting owners.
- New HTTP framing/server capability belongs in Lucent; AVPE owns only routes
  and game-specific semantics.
- New launcher commands compose modules under `src/avpe/`; discovery, build,
  and launch policy do not grow in `run.sh`.
- Reverse-engineered facts go in the relevant `docs/re/` contract and claims;
  goals, project state, and issues retain their separate authorities.
