# AVPE control channel (in-emulator lucent HTTP server)

The PCSX2 fork carries `pcsx2/AVPE/` — a loopback HTTP control channel built on
lucent (`3rdparty/lucent` submodule @ af80097, exception-free build support
added upstream). Started from QtHost after EmuThread::start(); port from env
`AVPE_HTTP_PORT` (default **28447**), bound strictly to 127.0.0.1.

## Endpoints

| Route | Body/Query | Effect |
|---|---|---|
| GET `/status` | — | `{"vm","serial","crc"}` |
| GET `/mem/read` | `addr=0xHEX&len=HEX` (≤4096) | EE bytes as hex (vtlb_ramRead, PINE-style) |
| GET `/mem/scan` | `start&end&hex=` (range ≤4MiB) | first 16 match addresses + hit count |
| GET `/debug` | — | `{"transfers","lastfifo","inject"}` host-side truth |
| POST `/mem/write` | `{"addr":"0x..","hex":"aabb.."}` | raw writes (vtlb_ramWrite) |
| POST `/state/save` | `{"path":"/abs/x.p2s"}` | CPU-thread save + flush |
| POST `/state/load` | `{"path":"/abs/x.p2s"}` | CPU-thread load |
| POST `/input/press` | `{"mask":512,"ms":250}` | PadDualshock2::Inputs bits, auto-expire |

Client tool: `uv run python tools/avpe_http.py <status|memread|memwrite|statesave|stateload|waitpointer|press|watch> ...`
Numbers in /input/press are DECIMAL (or "0x" strings); memread addr/len are hex.

## Verified live (SLUS-20147 boot, 2026-08-26)

- `/status` → Running / SLUS-20147 / 64DA78A3
- `/mem/read` byte-exact vs ELF file contents @0x00100000 (addressing proven)
- `/state/save` → scratch/states/title.p2s (4.9 MB); `/state/load` round-trips
- `/mem/write` read-back identical

## Known state of the game-side RE targets

- `pThe__11GAvPPointer` @0x00367720 stays NULL during FMVs and menus;
  constructed when a mission scene loads. Cursor injection therefore needs
  menu navigation first — pad-button injection now WORKS end-to-end (below).
- `pThe__12GInputDevice` @0x00366e68 is live on menus; device+0x34 = zmalloc'd
  CPS2Input* (0x45c bytes); port0 pad struct at CPS2Input+0x414; consumed
  button word (active-low u16) at +0x43E.

## Pad injection: proven, with the trap that cost a day

DS2 button data is ACTIVE-LOW. `GetButtons()` returns 0xFFFF when idle, so
OR-ing an injected mask is a silent no-op — the fix clears bits:
`return buttons & ~AVPE::ActiveButtonMask();`
The Inputs->wire translation mirrors PadDualshock2.h `bitmaskMapping`
(START=Inputs bit 9 -> wire bit 11). Verified live: press start,cross ->
SIO2 fifo `ff735af7bf...` and game-side btnword reads `f7bf`.
Claim C005. Menu-advance reaction still needs visual confirmation.
