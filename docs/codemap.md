# AVPE codemap

AVPE is organized as a locked Python launcher/controller around a maintained
PCSX2 fork. Host orchestration lives in `src/avpe/`; emulator-thread control and
native guest integration live in `thirdparty/pcsx2/pcsx2/AVPE/`; reverse-engineering
knowledge and evidence live under `docs/`.

Project intent is in [`project-goals.md`](project-goals.md), capability state is
in [`project-state.md`](project-state.md), and atomic work is in
[`issues/`](issues/). This file owns subsystem placement only.

## Ownership map

| Subsystem | Responsibility | Current or target location | Entry point | Deep doc |
|---|---|---|---|---|
| Launcher shim | Stable locked-environment entry | `run.sh` | `uv run --frozen avpe` | — |
| CLI orchestration | User commands, environment discovery, preflight | `src/avpe/cli.py` | `main()` | — |
| Emulator launch | PCSX2 argv, private config, process lifetime | `src/avpe/launch.py` | `launch()` | [headless contract](re/headless.md) |
| Project logging | Single Python log-level gate | `src/avpe/log.py` | `log()` | — |
| Disc conversion | Strict MODE2/2352 to ISO9660 conversion | `tools/raw2352.py` | `main()` | — |
| Control client | HTTP operations for state, memory, input, and snapshots | `tools/avpe_http.py` | `main()` | [control-channel contract](re/control-channel.md) |
| Control server | Loopback routes and VM/CPU-thread dispatch | `thirdparty/pcsx2/pcsx2/AVPE/AVPE.cpp/.h` | `AVPE::Start()` | [control-channel contract](re/control-channel.md) |
| EE-call execution | Guest-call queue, context, sentinel, and result handling | target: `thirdparty/pcsx2/pcsx2/AVPE/EECallShuttle.cpp/.h` | target: `AVPE::EECallShuttle` | [input-path contract](re/input-path.md) |
| Native input bridge | Keyboard/mouse translation into game-native functions | target: `thirdparty/pcsx2/pcsx2/AVPE/NativeInput.cpp/.h` | target: narrow route/input API | [input-path contract](re/input-path.md) |
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
├── raw2352.py                 disc-sector conversion
└── ghidra_scripts/            maintainer-only RE extraction
thirdparty/pcsx2/pcsx2/AVPE/   fork-side AVPE integration owner
docs/re/                       subsystem RE and operating contracts
docs/info/claims/              evidence ledger
docs/issues/                   atomic work and investigation points
```

## Where does new work go?

- Guest function invocation and EE register/PC lifetime belong in the dedicated
  fork-local `EECallShuttle` module, not the HTTP route implementation.
- Product keyboard/mouse semantics belong in the dedicated fork-local
  `NativeInput` module; host clients only send normalized intent.
- New HTTP framing/server capability belongs in Lucent; AVPE owns only routes
  and game-specific semantics.
- New launcher commands compose modules under `src/avpe/`; discovery, build,
  and launch policy do not grow in `run.sh`.
- Reverse-engineered facts go in the relevant `docs/re/` contract and claims;
  goals, project state, and issues retain their separate authorities.
