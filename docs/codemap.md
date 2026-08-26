# AVPE codemap

AVPE is organized as a native product host backed by a maintained PCSX2 fork,
with locked Python provisioning and test orchestration. The current in-process
host lives in the fork's AVPE Qt module; Python orchestration lives in
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
| Product launch | AVPE host argv, product config, process lifetime | `src/avpe/launch.py` | `launch()` | — |
| Native host shell | Sole visible top-level window, render-surface lifecycle, resize/fullscreen, focus, product shutdown | `thirdparty/pcsx2/pcsx2-qt/AVPE/HostWindow.cpp/.h` | `-avpe-host`; `AVPE::HostWindow` | [presentation](host/presentation.md) |
| Presentation bridge | GS-to-host window acquisition now; future same-frame RmlUi composition and narrow display/settings control | current: `pcsx2-qt/QtHost.cpp` signal boundary; target: `pcsx2/AVPE/PresentationBridge.cpp/.h` | `Host::AcquireRenderWindow()` | [presentation](host/presentation.md) |
| Control-test runner | Silent surfaceless PCSX2 process, isolated profile, timebox, exact process-group cleanup | `tools/run_control_test.py` | `main()` | [control-test contract](re/headless.md) |
| Project logging | Single Python log-level gate | `src/avpe/log.py` | `log()` | — |
| Disc conversion | Strict MODE2/2352 to ISO9660 conversion | `tools/raw2352.py` | `main()` | — |
| Control client | HTTP operations for state, memory, input, and snapshots | `tools/avpe_http.py` | `main()` | [control-channel contract](re/control-channel.md) |
| Control server | Loopback routes and VM/CPU-thread dispatch | `thirdparty/pcsx2/pcsx2/AVPE/AVPE.cpp/.h` | `AVPE::Start()` | [control-channel contract](re/control-channel.md) |
| EE-call execution | Guest-call queue, context, return-PC stop, budget, and result handling | `thirdparty/pcsx2/pcsx2/AVPE/EECallShuttle.cpp/.h` | `AVPE::EECallShuttle` | [input-path contract](re/input-path.md) |
| Native input bridge | Keyboard/mouse translation into game-native functions | target: `thirdparty/pcsx2/pcsx2/AVPE/NativeInput.cpp/.h` | target: narrow route/input API | [input-path contract](re/input-path.md) |
| Native save bridge | AVP:E save-boundary interception, schema translation, atomic host persistence, and one-time card import | target: `thirdparty/pcsx2/pcsx2/AVPE/NativeSaves.cpp/.h` | target: `AVPE::NativeSaves` | target: `docs/re/save-path.md` |
| Native asset I/O | AVP:E file/sector mapping, validated disc-derived asset store, asynchronous host reads, cache, and optical-path bypass | target: `thirdparty/pcsx2/pcsx2/AVPE/NativeAssets.cpp/.h`; narrow hooks in the grounded CDVD/IOP boundary | target: `AVPE::NativeAssets` | target: `docs/re/disc-io.md` |
| AVP:E-specific HLE BIOS | Required firmware-service inventory, clean-room EE kernel/BIOS behavior, IOP/module services, and BIOS-free boot policy | target: `thirdparty/pcsx2/pcsx2/AVPE/HLE/`; narrow hooks at existing BIOS/IOP service owners | target: `AVPE::HLE` | target: `docs/re/hle-bios.md` |
| Native options UI | RmlUi lifecycle, options documents, and game-facing settings bindings | target: `thirdparty/pcsx2/pcsx2-qt/AVPE/UI/` | target: `AVPE::NativeSettingsUI` | target: `docs/ui/options.md` |
| Diagnostic pad injection | Bootstrap-only active-low DS2 injection | `thirdparty/pcsx2/pcsx2/SIO/Pad/PadDualshock2.cpp` | `GetButtons()` integration | [control-channel contract](re/control-channel.md) |
| RE helpers | Ghidra extraction, caller discovery, singleton inventory | `tools/ghidra_scripts/`, `tools/pthe_syms.txt` | individual tools | [input-path contract](re/input-path.md) |
| Evidence | Falsifiable claims and verification dependencies | `docs/info/claims/` | claim files | — |

## Source map

```text
run.sh                         locked launcher shim
src/avpe/                      host-side product orchestration
├── cli.py                     command and prerequisite owner
├── launch.py                  emulator process/config owner
└── log.py                     Python logging owner
tools/                         project automation and control clients
├── avpe_http.py               live control client
├── run_control_test.py        surfaceless and silent test process owner
├── raw2352.py                 disc-sector conversion
└── ghidra_scripts/            maintainer-only RE extraction
thirdparty/pcsx2/pcsx2/AVPE/   fork-side AVPE integration owner
thirdparty/pcsx2/pcsx2-qt/AVPE current native host-window owner
docs/re/                       subsystem RE and operating contracts
docs/info/claims/              evidence ledger
docs/issues/                   atomic work and investigation points
```

## Where does new work go?

- Guest function invocation and EE register/PC lifetime belong in the dedicated
  fork-local `EECallShuttle` module, not the HTTP route implementation.
- Product keyboard/mouse semantics belong in the dedicated fork-local
  `NativeInput` module; host clients only send normalized intent.
- AVP:E save interception, schema translation, atomic files, and memory-card
  import belong in the dedicated fork-local `NativeSaves` module; generic PCSX2
  card emulation remains outside that owner.
- AVP:E asset resolution, native storage, async reads, and caching belong in
  the fork-local `NativeAssets` module. Grounded CDVD/IOP hooks call that owner;
  they do not absorb game-specific file tables or host I/O policy.
- AVP:E-specific firmware behavior belongs under the fork-local `AVPE/HLE/`
  owner. Existing BIOS, EE kernel, and IOP integration points remain narrow
  hooks; they do not become a second copy of the game-specific service model.
- The visible native window and its platform lifecycle belong in the fork's
  `pcsx2-qt/AVPE/` host module. PCSX2's generic `MainWindow` remains hidden and
  administrative; it does not own product presentation.
- RmlUi documents and input routing belong under `pcsx2-qt/AVPE/UI/` while the
  host remains in-process. Their interfaces must stay independent of
  `MainWindow` so a future standalone `src/host/` executable can reuse them.
- The fork-side presentation bridge belongs in `pcsx2/AVPE/` and exposes only
  frame and settings operations needed by the host; graphics/display
  validation and application continue to call existing PCSX2 setting owners.
- New HTTP framing/server capability belongs in Lucent; AVPE owns only routes
  and game-specific semantics.
- New launcher commands compose modules under `src/avpe/`; discovery, build,
  and launch policy do not grow in `run.sh`.
- Reverse-engineered facts go in the relevant `docs/re/` contract and claims;
  goals, project state, and issues retain their separate authorities.
