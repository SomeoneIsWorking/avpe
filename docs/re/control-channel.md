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
| POST `/mem/write` | `{"addr":"0x..","hex":"aabb.."}` | raw writes (vtlb_ramWrite) |
| POST `/state/save` | `{"path":"/abs/x.p2s"}` | CPU-thread save + flush |
| POST `/state/load` | `{"path":"/abs/x.p2s"}` | CPU-thread load |

Client tool: `uv run python tools/avpe_http.py <status|memread|memwrite|statesave|stateload|waitpointer> ...`

## Verified live (SLUS-20147 boot, 2026-08-26)

- `/status` → Running / SLUS-20147 / 64DA78A3
- `/mem/read` byte-exact vs ELF file contents @0x00100000 (addressing proven)
- `/state/save` → scratch/states/title.p2s (4.9 MB); `/state/load` round-trips
- `/mem/write` read-back identical

## Known state of the game-side RE targets

- `pThe__11GAvPPointer` @0x00367720 stays NULL during FMVs and menus;
  constructed when a mission scene loads. Cursor injection therefore needs
  menu navigation first — next step is synthetic button injection through the
  CPS2Input per-port struct (offsets in docs/re/input-path.md), driven over
  this channel.
- `pThe__12GInputDevice` @0x00366e68 is live on menus (0x0155E7D0 observed);
  backend object at [device+0x34].
