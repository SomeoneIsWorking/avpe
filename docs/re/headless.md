# Surfaceless control-test contract

Recipe: `uv run --frozen python tools/run_control_test.py --seconds N`.
`run.sh` is exclusively the user-facing product launcher and is not a test
interface.

## What failed

`-batch -nogui` hides PCSX2's main UI but does **not** suppress its game render
surface. The user observed that window, falsifying C003 and the previous version
of this document. Null audio and a software renderer do not change display
surface ownership.

## Required test behavior

- `tools/run_control_test.py` owns its process and never calls `run.sh`.
- The recognized `-avpe-control-test` application mode is consumed before
  render-window acquisition and forces PCSX2's actual
  `WindowInfo::Type::Surfaceless` path. An old binary rejects the flag.
- `QT_QPA_PLATFORM=offscreen` is set and `DISPLAY` / `WAYLAND_DISPLAY` are
  removed, so the child cannot connect to the user's desktop.
- The isolated test profile under `scratch/control-test/` selects null audio,
  disables memory cards, and never mutates product settings.
- Save-boundary runs may explicitly pass `--memory-card-source CARD.ps2`. The
  runner copies it into the isolated profile, enables only that working copy,
  verifies the source hash is unchanged, and records byte-level changes in
  `scratch/control-test/memory-card-proof.json`. Memory cards remain disabled
  when the option is absent.
- Native I/O recovery runs select exactly one of
  `--probe-native-ioman-state-recovery` or
  `--probe-native-cdvd-state-recovery`. They use clean boot, a copied card,
  shipping `/state/save` and `/state/load`, and ignored state/proof artifacts
  under `scratch/control-test/`; they never reuse `--statefile` input.
- `--use-native-assets` admits the validated native store without selecting a
  probe, leaving the control process alive for the requested timebox so a
  maintainer can exercise new clean-boot routes through `tools/avpe_http.py`.
- `--probe-native-marine-m1-transition` waits for the clean-boot native stream
  boundary, stages `M01/background.tbd` through `CShell::SetNextLevel`, and
  proves the real M1 world endpoint without an input savestate or pad
  injection. `tools/compare_native_load_timing.py --target mission` composes
  that route with the exact `ShellLoadLevel` timing sample.
- Each run reserves an available loopback port and generates a nonce. Success
  requires the child to echo that nonce plus its actual `control-test`,
  `surfaceless`, and `null-muted` runtime state, target serial, and CRC.
- Normal teardown uses `POST /shutdown` and the VM/UI lifecycle. PID-scoped
  TERM/KILL is fallback cleanup only; signal-driven teardown is not accepted as
  a successful test.
- Boot evidence lives under `scratch/control-test/logs/` and must include real
  SLUS-20147 activity plus a live control-channel status response.

## Gotchas that cost us time — do not re-derive

1. `-datapath X` stores config under `X/PCSX2/` (not `X/`). Seeding `X/inis`
   silently does nothing.
2. PCSX2 flags are SINGLE-dash (`-help`, `-version`, `--version` is unknown →
   boots the GUI instead).
3. A fresh datapath needs both the current `UI/SettingsVersion` and
   `UI/SetupWizardIncomplete=false`. Omitting the version enters the invisible
   invalid-settings question; omitting the setup flag enters the invisible
   setup wizard. `ensure_test_config` owns both in the isolated profile.
4. Diagnostic trick: main-thread gdb bt of a stuck pcsx2-qt names the blocking
   dialog immediately (`QtHost.cpp:2514 -> RunSetupWizard -> QDialog::exec`).
5. Renderer selection is not a headless mechanism. Only the host's surfaceless
   contract prevents native surface creation; Audio Null independently
   guarantees silence.
6. SIGTERM is not normal teardown. PCSX2 treats it as Ctrl+C, may enter generic
   dialog-driven shutdown, and can abort under the offscreen plugin. Use the
   control channel's VM shutdown route.

## Deterministic shim-test input

Use `-statefile` to load a savestate taken just past FMVs so every shim test
boots into the same gameplay moment.
