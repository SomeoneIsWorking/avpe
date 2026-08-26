# AVPE project state

This is the authoritative current inventory of verified, partial, blocked, and
missing capabilities. Epic intent is in [`project-goals.md`](project-goals.md),
atomic work in [`issues/`](issues/), and ownership in
[`codemap.md`](codemap.md).

States: `verified` means the stated capability was observed with durable
evidence; `partial` names the demonstrated subset and exact gap; `blocked`
names the issue or unavailable state item preventing completion; `missing`
means the capability is absent.

## Current focus

**S010 — game-native menu input.** Directional navigation, activation, cancel,
and the product keyboard mapping exist through typed game-native owners. The
next grounded input step is menu mouse hit-testing and broader menu coverage.
Current focus is attention, not a separate state.

## Capability inventory

| ID | Capability or outcome | State | Factual dependency | Goals |
|---|---|---|---|---|
| S001 | Project preflight, user-asset discovery, and disc conversion | verified | — | G001 |
| S002 | Game-native input and pointer architecture map | verified | S001 | G002 |
| S003 | Maintained PCSX2 fork and dependency stack build the current AVPE integration | verified | S001 | G001 |
| S004 | Isolated surfaceless and silent control-test path boots the target | verified | S003 | G001 |
| S005 | Live control, memory, savestate, diagnostic input, and snapshot channel | verified | S004 | G001, G002 |
| S006 | Reproducible mission state and identified live rendered cursor | verified | S005 | G001, G002 |
| S007 | Reusable VM-thread EE-call shuttle | verified | S005, S006 | G002 |
| S008 | Native absolute pointer injection moves the rendered cursor | verified | S007 | G002 |
| S009 | Native mouse selection and command clicks | verified | S007, S008 | G002 |
| S010 | Keyboard and mouse menu navigation through game-native paths | partial | S009; issue #6 | G002 |
| S011 | Selector, camera, minimap, and pointer-mode integration | missing | S008, S009 | G002 |
| S012 | Fresh-clone provisioning through the zero-argument launcher | missing | S003, S004 | G001 |
| S013 | End-to-end windowed product playable with native PC RTS controls | blocked | S009, S010, S011, S012, S020 | G001, G002 |
| S014 | AVP:E save/load boundary and on-card data schema | missing | S001 | G003 |
| S015 | Atomic versioned PC-native save backend for AVP:E profiles and slots | blocked | S014 | G003 |
| S016 | Game save/load path operates without a virtual PS2 memory card | blocked | S014, S015 | G001, G003 |
| S017 | Existing AVP:E memory-card progress imports into native saves | blocked | S014, S015 | G003 |
| S018 | RmlUi native options surface is integrated into the AVPE host shell | missing | S020 | G004 |
| S019 | Graphics, display, and resolution settings enumerate, apply, and persist | blocked | S018 | G004 |
| S020 | AVPE-owned host shell owns the visible window and presentation lifecycle | partial | S003, S004 | G001, G004 |
| S021 | AVP:E disc/file access boundary and asset namespace are mapped | missing | S001 | G005 |
| S022 | User disc content provisions into a validated native asset store | blocked | S021 | G001, G005 |
| S023 | Supported game asset requests use native host storage instead of emulated optical I/O | blocked | S021, S022 | G001, G005 |
| S024 | Native asset I/O preserves behavior and measurably reduces loading time | blocked | S023 | G005 |
| S025 | AVP:E's required BIOS, kernel, and IOP service surface is inventoried | missing | S001, S004 | G006 |
| S026 | Clean-room AVP:E-specific HLE implements the required platform services | blocked | S025 | G006 |
| S027 | Supported target boots and runs without retail BIOS bytes | blocked | S026 | G001, G006 |
| S028 | HLE behavior is differentially verified against the BIOS-backed oracle | blocked | S025, S026 | G006 |

## State details and evidence

### S001 — preflight, assets, and disc conversion: verified

Observed subset: the locked Python project, slim launcher, actionable preflight,
asset environment contract, and strict disc-to-ISO extraction path exist.

Evidence: commit `6a94e4f`; `run.sh`, `.env.example`, `src/avpe/cli.py`,
`tools/raw2352.py`, and the positive/negative doctor evidence in resolved issue
#2.

### S002 — input architecture map: verified

Observed capability: the relevant game-native input, pointer, selector, camera,
and click functions and singleton addresses are mapped from the target binary.

Evidence: claim C002 and [`re/input-path.md`](re/input-path.md).

### S003 — current PCSX2 build: verified

Observed capability: `deps.toml` names the upstream base, maintained fork URL,
and exact fork revision. That revision builds the AVPE host, isolated control
runtime, and EE-call shuttle with Clang against the project dependency prefix.
The claim checker reports C001 as a coarse file-change advisory, not as
evidence that the earlier baseline-build claim was falsified.

Evidence: claims C001, C004, C007–C009; project commits `6a94e4f` and
`577042c`; PCSX2 fork commit `6c39381`; successful `pcsx2-qt` Clang build.

### S004 — isolated control-test launch: verified

Observed capability: the dedicated `tools/run_control_test.py` path boots the
target with PCSX2's actual surfaceless host contract, Qt offscreen with desktop
display variables removed, null and muted audio, an isolated datapath, a
per-run loopback port and nonce, and graceful VM shutdown. Runtime status
reported `control-test`, `surfaceless`, `null-muted`, `SLUS-20147`, and CRC
`64DA78A3`; deliberately altered status fixtures for native display, real
audio, and a different nonce were all rejected.

Evidence: claim C007, instrument I001, and [`re/headless.md`](re/headless.md).

### S005 — live control channel: verified

Observed capability: the emulator exposes loopback-only status, EE memory,
savestate, diagnostic input, and frame-snapshot operations, with matching and
differing live observations.

Evidence: claims C004–C006 and
[`re/control-channel.md`](re/control-channel.md). The claim checker cannot see
the ignored fork files named by C004–C005, so those dependencies require manual
re-validation after fork changes.

### S006 — mission and cursor: verified

Observed capability: automation reaches an in-mission state, saves and loads
that state, locates the live `GMarinePointer`, and demonstrates that direct
screen-position writes do not move the world-position-rendered cursor.

Evidence: claims C005–C006 and the savestate/snapshot evidence named there.

### S007 — EE-call shuttle: verified

Observed subset: the fork-local shuttle executes on the VM thread, preserves EE
architectural context, stops the interpreter or recompiler at the requested
return PC, applies a cycle budget, and fail-closes after a timeout until a
successful state load. A real boot invoked `CRenderer::GetResolution` at
`0x00137b30` in 19 cycles and returned `0x003c9fe0`; the pointed structure read
`0, 0, 640, 448`. Invalid targets, a one-cycle timeout, the post-timeout gate,
and reset through a successful state load all produced distinct expected
results.

The same positive and negative controls were repeated through the verified
surfaceless runner. Evidence: claim C008 and resolved issue #1.

### S008 — absolute cursor movement: verified

Observed capability: `NativeInput::MoveAbsolute` validates normalized intent,
the current resolution and live game pointer, reasserts absolute input mode,
stages the exact eight-byte `CInputData` argument in guest main RAM, invokes the
game's function, and restores the interrupted stack bytes and architectural
context. The verified surfaceless runner rendered stable cursor centers at
`(128.48,95.06)` and `(512.35,94.71)`. Both calls attested exact staging
restoration at the same nonzero staging address; an out-of-range request
returned 400 and left the second rendered position unchanged.

Evidence: claim C009, instrument I002, resolved issue #4, and
`scratch/control-test/pointer-proof.json` (ignored per-run artifact).

### S009 — mouse actions: verified

Observed capability: typed primary and secondary button edges invoke AVP:E's
original four mouse handlers through the EE-call transaction owner. A primary
press/release at `(240,340)` changed the selected object from `0x01993540` to
`0x01975240`. A secondary release at `(100,100)` kept that object selected and
changed its game-owned current-command field from zero to move-message ID
`0x00060039`. Duplicate releases, duplicate presses, an unknown button, an
invalid live pointer, and a release after savestate-reset all failed with the
expected 400/409 responses.
The combined pointer/action probe then completed graceful surfaceless,
null-muted shutdown with exit status zero.

Evidence: claim C010, instrument I003, resolved issue #5, and
`scratch/control-test/mouse-proof.json` (ignored per-run artifact).

### S010 — menu navigation: partial

Observed subset: `NativeMenuInput` discovers the unique active `GMenu` owner
from AVP:E's live `GInputDevice` callback registry and resolves focused items
through the game handle table. Returning directional calls changed pause-menu
focus from Resume (`0x015DFB60`) to Save (`0x015E0640`). Activation and cancel
now queue deferred guest calls through the ordinary VM scheduler and restore
the interrupted EE/FPU/VU0 context plus exact reserved stack bytes at the
return PC. Press START activation replaced menu `0x01346590` with
`0x0147D230`; pause Save activation replaced `0x012E85A0` with `0x015AFA70`,
and virtual cancel restored `0x012E85A0`. Both isolated runs were surfaceless,
null-muted, and shut down gracefully. The product `HostInputRouter` maps
arrows/WASD, Enter/Space, and Escape/Backspace to these typed actions without
DualShock emulation.

Gap: the real windowed key-event path remains unobserved because agent tests
must be windowless; menu mouse hover/hit-testing is absent; and title, mission,
and in-game menu coverage remains incomplete.

Evidence: claims C011–C012, instrument I004, issue #6, and
`scratch/control-test/menu-proof.json` (ignored per-run artifact).

### S011 — selector and camera integration: missing

Missing capability: runtime evidence is required across selector
method changes, camera motion, minimap behavior, and pointer-mode transitions.

### S012 — fresh-clone launcher: missing

Missing capability: from a cold checkout with documented native dependencies,
`uv`, and user assets, `./run.sh` must provision portable dependencies/build
outputs and launch the windowed product without Ghidra or undocumented steps.

### S013 — playable native-input product: blocked

Blockers: S009–S012 and S020. Verification requires a clean windowed run through
representative menu, click/drag selection, right-click contextual command,
keyboard-shortcut, camera, and minimap interactions using a coherent
StarCraft-informed PC RTS control scheme.

### S014 — save boundary and schema: missing

Missing capability: identify the game functions that enumerate, validate,
serialize, deserialize, and commit AVP:E save data; map the on-card records and
checksums from the executable plus at least two deliberately differing real
saves.

### S015 — native save backend: blocked

Blocker: S014. Verification requires versioned host files with atomic replace,
positive round-trips for distinct data, and negative controls for truncated,
corrupt, and incompatible input using the shipping parser/writer.

### S016 — memory-card-free game path: blocked

Blockers: S014 and S015. Verification requires saving, restarting, and loading
distinct progress while no virtual memory card is configured, with no card UI
or card-format prompt reachable in the normal product path.

### S017 — existing-save import: blocked

Blockers: S014 and S015. Verification requires importing at least two distinct
real AVP:E saves from a user-selected memory-card image, preserving their
observable progress, and refusing unrelated or malformed card data by name.

### S018 — RmlUi options surface: missing

Missing capability: RmlUi is not integrated into AVPE's windowed render/input
lifecycle, and the normal product has no project-owned native options screen.
Verification requires opening and closing the real overlay repeatedly while the
game runs, with correct keyboard, mouse, focus, resize, and render behavior.

### S019 — native graphics and display settings: blocked

Blocker: S018. Verification requires enumerating supported modes, applying at
least two deliberately distinct resolution/display configurations through the
shipping PCSX2 setting owners, rejecting an unsupported choice, and observing
the selected configuration after a clean restart.

### S020 — AVPE host shell: partial

Observed subset: `AVPE::HostWindow` is a dedicated top-level product window;
`-avpe-host` keeps PCSX2's administrative `MainWindow` hidden and routes render
acquire/release, resize, mouse mode, and mouse lock exclusively to the AVPE
owner. The default product launcher requires this mode, and the Clang build plus
offscreen command-line capability check pass.

Gap: respecting the user's no-window test constraint means the real desktop
window has not been launched in this session. Runtime verification still must
exercise resize, fullscreen, focus, close, and failure reporting without any
generic PCSX2 dialog escaping. Input routing and RmlUi same-frame composition
are also missing. Atomic work: issue #3.

### S021 — disc/file access boundary: missing

Missing capability: identify the EE/IOP functions, file tables, archive
formats, sector mappings, asynchronous completion rules, and error paths that
connect AVP:E asset requests to the emulated optical drive.

### S022 — native asset provisioning: blocked

Blocker: S021. Verification requires deriving the supported asset set from a
user-supplied disc image into a versioned, validated native store, refusing the
wrong revision and corrupt or incomplete content by name, and never tracking
copyrighted bytes.

### S023 — native asset reads: blocked

Blockers: S021 and S022. Verification requires representative game asset loads
to complete through the project-owned host I/O path with emulated optical
seeks and sector-timed transfers absent from the same trace. Byte content,
ordering, short reads, and errors must still match the grounded game contract.

### S024 — loading behavior and performance: blocked

Blocker: S023. Verification requires repeatable cold-cache and warm-cache
measurements across startup, mission load, and representative transitions,
plus negative controls proving that missing or corrupt native assets fail
loudly rather than silently falling back to a slower or semantically different
disc path.

### S025 — required firmware service inventory: missing

Missing capability: trace and catalogue the exact BIOS syscalls, EE kernel
services, interrupts, timers, executable-loader behavior, and IOP modules used
by the supported target across boot, menus, missions, saves, and shutdown.

### S026 — AVP:E-specific HLE implementation: blocked

Blocker: S025. Verification requires project-owned clean-room implementations
of the inventoried contracts, with deliberately exercised success, error,
timing, and ordering behavior and loud refusal of unknown services.

### S027 — BIOS-free product path: blocked

Blocker: S026. Verification requires a clean product profile with no retail
BIOS file present to boot the target and complete representative menu, mission,
save/load, and shutdown sequences without a firmware fallback.

### S028 — HLE differential fidelity: blocked

Blockers: S025 and S026. Verification requires deterministic comparisons of
service results, guest-visible state, interrupts, and timing against the
current BIOS-backed oracle, including cases that must differ and explicit
residuals for any accepted non-semantic timing variance.
