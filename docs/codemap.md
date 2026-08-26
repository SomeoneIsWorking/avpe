# AVPE codemap

RE-driven PCSX2 C++ mod port of *Aliens Versus Predator: Extinction* (PS2, SLUS_201.47) to PC.
No recomp, no pad-emulation wrapper: a fork of PCSX2 gains an in-tree shim that drives the
game's own pointer/input structures directly from native keyboard/mouse.

## Layout

| Path | What |
|---|---|
| `run.sh` | slim shim -> `uv run --frozen avpe <cmd>` (doctor default until launch exists) |
| `src/avpe/cli.py` | `doctor` preflight (real checks, actionable refusals); more subcommands coming |
| `src/avpe/log.py` | single logger, AVPE_LOG level gate lives here only |
| `tools/raw2352.py` | MODE2/2352 -> ISO9660 stripper; verifies every sector sync, aborts loudly |
| `deps.toml` | fork dependency manifest (pcsx2 pinned rev e1dd0a08599e86a9928a83b84923bce12a59aba7) |
| `thirdparty/pcsx2/` | cloned upstream (gitignored until fork remote exists; then submodule pin) |
| `scratch/iso/elf/SLUS_201.47` | extracted game ELF (copyrighted — never leave repo tree via git) |
| `scratch/build/`, `scratch/logs/`, `scratch/ghidra/` | build output, logs, Ghidra project |

## Status

- [x] Scaffold + doctor
- [x] CHD extracted & verified; ELF has full symtab (~15k symbols, NOT stripped)
- [x] Ghidra: r5900 import (emotionengine-reloaded ext) — see docs/re/input-path.md
- [x] Input architecture mapped to function-level (CPS2Input/GInputDevice/GfsPointer)
- [x] Qt+deps self-build (scratch/deps) via upstream CI script
- [x] PCSX2 baseline build at scratch/build/bin/pcsx2-qt
- [x] HEADLESS BOOT VERIFIED: `./run.sh launch --seconds N` boots SLUS_20147
      (FMVs play, NTSC vsync ticks, clean SIGTERM shutdown). Audio = Null stream,
      all windows hidden under -nogui. Gotchas recorded in docs/re/headless.md
- [ ] Dynamic verify: selector mode, injected cursor movement

## Verification commands

- `./run.sh doctor` — preflight; every failure names the exact fix
- `uv run python tools/raw2352.py <bin> <iso>` — sector-exact strip, refuses bad sync
