# Headless run notes (pcsx2-qt, this project)

Recipe: `./run.sh launch [--seconds N] [--windowed]` → see src/avpe/launch.py.

## What "headless" means here (verified 2026-08-26)

- `-batch -nogui`: main window never shown; the GS surface lives inside it, so
  nothing appears and nothing takes focus. Even HW (Vulkan) render stays invisible.
- `[SPU2/Output] Backend = Null` → "Creating Null audio stream" in emulog; no
  audio device touched.
- Boot evidence to look for in scratch/logs/emulog.txt:
  `(SYSTEM.CNF) Software version`, `FMV started/ended`,
  `Add N seconds play time to SLUS-20147`, NTSC CRTC/vsync lines.

## Gotchas that cost us time — do not re-derive

1. `-datapath X` stores config under `X/PCSX2/` (not `X/`). Seeding `X/inis`
   silently does nothing.
2. PCSX2 flags are SINGLE-dash (`-help`, `-version`, `--version` is unknown →
   boots the GUI instead).
3. A fresh datapath gets `UI/SetupWizardIncomplete=true` written by PCSX2 on
   first default-config creation. In `-nogui` the setup wizard then runs as an
   INVISIBLE modal and blocks startup forever (CPU Thread idle in event loop,
   main thread in QDialog::exec). ensure_config forces it False.
4. Diagnostic trick: main-thread gdb bt of a stuck pcsx2-qt names the blocking
   dialog immediately (`QtHost.cpp:2514 -> RunSetupWizard -> QDialog::exec`).
5. `Renderer = 11/13` does not change device init: Vulkan is still opened for
   presentation (hidden). Audio-Null is what guarantees silence.

## Next step for deterministic shim testing

Use `-statefile` to load a savestate taken just past FMVs so every shim test
boots into the same gameplay moment.
