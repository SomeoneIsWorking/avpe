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
- [x] HEADLESS BOOT VERIFIED: `./run.sh launch --headless --seconds N`
- [x] CONTROL CHANNEL LIVE: fork @68402a7 + lucent @af80097 — see
      docs/re/control-channel.md; client `tools/avpe_http.py` (claims C004/C005)
- [x] /snap endpoint: headless VISION — BMP of current frame (claim C006)
- [x] MISSION REACHED: title -> start -> M1 briefing -> start -> gameplay;
      savestates: title-real.p2s (post-FMV), mission1.p2s (in-mission)
- [x] Cursor located: live object is GMarinePointer (GAvPPointer subclass),
      pos floats at obj+0x194/198 verified =screen center
- [ ] EE-CALL SHUTTLE (now required): screen-pos writes don't move the sprite
      (renders from world pos); must call Input_UpdatePositionAbsolute
- [ ] KB&M menu support (GfsPointer absolute path + menu hit-testing)
- [ ] Dynamic verify: selector mode, injected cursor movement

## Verification commands

- `./run.sh doctor` — preflight; every failure names the exact fix
- `uv run python tools/raw2352.py <bin> <iso>` — sector-exact strip, refuses bad sync
