# AVPE control channel (in-emulator lucent HTTP server)

The PCSX2 fork carries `pcsx2/AVPE/` — a loopback HTTP control channel built on
lucent (`3rdparty/lucent` submodule @ af80097, exception-free build support
added upstream). Started from QtHost after EmuThread::start(); port from env
`AVPE_HTTP_PORT` (default **28447**), bound strictly to 127.0.0.1.

## Endpoints

| Route | Body/Query | Effect |
|---|---|---|
| GET `/status` | — | VM identity plus `host_mode`, `surface`, `audio`, and per-run `nonce` |
| GET `/mem/read` | `addr=0xHEX&len=HEX` (≤4096) | EE bytes as hex (vtlb_ramRead, PINE-style) |
| GET `/mem/scan` | `start&end&hex=` (range ≤4MiB) | first 16 match addresses + hit count |
| GET `/debug` | — | `{"transfers","lastfifo","inject"}` host-side truth |
| GET `/memory-card/state` | — | CPU-thread slot-0 presence, savestate auto-eject ticks, busy state, and derived readiness |
| GET `/bios/trace` | — | current bounded BIOS/IOP observation snapshot |
| GET `/input/dispatch` | — | bounded normal `GInputDevice` callback-dispatch identities and pending/completed diagnostic actions |
| POST `/bios/trace/start` | `{}` | clear and enable the bounded BIOS/IOP sink for a new phase |
| POST `/bios/trace/capture` | `{}` | atomically snapshot and disable the BIOS/IOP sink |
| POST `/mem/write` | `{"addr":"0x..","hex":"aabb.."}` | raw writes (vtlb_ramWrite) |
| POST `/state/save` | `{"path":"/abs/x.p2s"}` | CPU-thread save + flush; success includes the native asset state captured immediately before serialization |
| POST `/state/load` | `{"path":"/abs/x.p2s"}` | CPU-thread load; success includes the native asset state captured immediately after restoration |
| POST `/guest/reset` | `{}` | CPU-thread real VM reset; success includes pre/post native state and the bounded cache snapshot |
| POST `/input/press` | `{"mask":512,"ms":250}` | PadDualshock2::Inputs bits, auto-expire |
| POST `/input/move-absolute` | `{"x":0.5,"y":0.5}` | normalized coordinates through the game-native absolute-pointer owner |
| POST `/input/mouse-button` | `{"button":"primary","edge":"press"}` | typed edge through the corresponding original AVP:E mouse handler |
| GET `/input/menu` | — | read-only active AVP:E menu owner, callback count, and focus |
| POST `/input/menu-action` | `{"action":"down"}` | typed direction, activate, or cancel through the active AVP:E `GMenu` owner |
| GET `/input/menu-pointer` | — | read-only active menu-capable pointer owner and focused item |
| POST `/input/menu-pointer-move` | `{"x":0.7,"y":0.4}` | absolute motion followed by deferred AVP:E menu hit-testing |
| POST `/input/menu-pointer-activate` | `{}` | deferred activation through the focused menu pointer item |
| GET `/ee/deferred` | — | current deferred guest-call identity, completion, and restoration evidence |
| POST `/ee/call` | `{"function":"0x..","a0":"0x..",...,"cycle_budget":N}` | bounded VM-thread guest call through the AVPE EE-call shuttle |
| POST `/shutdown` | `{}` | graceful VM shutdown for the isolated control-test owner |

Client tool: `uv run python tools/avpe_http.py <status|memread|memwrite|statesave|stateload|eecall|waitpointer|press|moveabsolute|mousebutton|menuaction|menupointerstate|menupointermove|menupointeractivate|watch> ...`
Numbers in /input/press are DECIMAL (or "0x" strings); memread addr/len are hex.
`POST /input/press` schedules an asynchronous hold. Probe code uses the shared
`press_buttons()` lifecycle observer, which requires `/debug` to show both the
requested active-low mask and its release before it returns; the HTTP response
alone is not completion evidence.

Agent and maintainer runtime verification enters through
`tools/run_control_test.py`, never `run.sh`. The runner allocates a loopback
port and nonce, removes desktop display sockets from the child environment,
uses an isolated settings profile, and accepts the process only when `/status`
reports the actual `control-test` / `surfaceless` / `null-muted` runtime state.
The nonce prevents a stale or unrelated process from satisfying the check.
Guest/menu and memory-card routes refuse with HTTP 409 before a valid VM exists;
they never dispatch synchronously onto an unstarted emulation thread.
When a copied memory card accompanies a savestate, the runner also waits for
`/memory-card/state` to report the card present, its 60-frame auto-eject expired,
and no write busy state before driving the title. Before shutdown it waits for
the observed 300-frame post-write busy interval to clear, so a successful
process exit cannot hide an unflushed card operation.

## Verified live (SLUS-20147 boot, 2026-08-26)

- `/status` → Running / SLUS-20147 / 64DA78A3
- `/mem/read` byte-exact vs ELF file contents @0x00100000 (addressing proven)
- `/state/save` → scratch/states/title.p2s (4.9 MB); `/state/load` round-trips
- Live native recovery runs use the same routes and require exact atomic
  `native_asset_state` equality across save/load: descriptor fd/path/cursor,
  CDVD path/base-LSN/size/SHA-256, next-LSN, and zero active completion tokens.
- `/mem/write` read-back identical
- `/ee/call` invoked `CRenderer::GetResolution` at `0x00137b30`, returned
  `v0=0x003c9fe0` after 19 cycles, and the pointed structure read
  `0,0,640,448`; a one-cycle limit timed out and fail-closed later calls until
  a successful state load reset the shuttle.
- `/input/move-absolute` moved the live rendered cursor from `(128.48,95.06)`
  to `(512.35,94.71)` through `NativeInput`, with exact temporary-stack
  restoration attested at the same nonzero address for both calls; an
  out-of-range request returned 400 and the next coherent snapshot retained
  the second position.
- `/input/mouse-button` primary press/release changed selected object identity
  from `0x01993540` to `0x01975240`; secondary release retained the selected
  object and recorded AVP:E's move-message ID `0x60039` in its current-command
  field. Duplicate and unmatched edges fail with 409, unknown button names fail
  with 400, an invalid live pointer fails with 409, and state load clears
  held-edge state.
- `/input/menu-action` changed pause focus from Resume (`0x015DFB60`) to Save
  (`0x015E0640`), activated Save through deferred `GMenu::Input`, then invoked
  the destination menu's virtual cancel handler. Ownership changed
  `0x012E85A0 -> 0x015AFA70 -> 0x012E85A0`; both deferred calls restored their
  exact guest stack frames. An earlier Press START activation changed
  `0x01346590 -> 0x0147D230`, but a later identical saved-state run completed
  and restored the deferred guest call without changing the active menu; that
  saved-state transition is therefore not deterministic evidence.
- `/input/menu-pointer-move` used the active callback-owned pointer
  `0x015FE940` and AVP:E's own hit-test to focus Resume (`0x015DFB60`) at
  normalized `(0.7,0.3)` and Save (`0x015E0640`) at `(0.7,0.4)`. An invalid
  coordinate returned 400 without queuing work. Pointer activation then
  entered menu `0x015AFA70` through a deferred call with exact stack restore.

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
