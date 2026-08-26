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

**S007 — reusable EE-call shuttle.** It is currently `missing`; issue #1 is the
active atomic work point. Current focus is attention, not a separate state.

## Capability inventory

| ID | Capability or outcome | State | Factual dependency | Goals |
|---|---|---|---|---|
| S001 | Project preflight, user-asset discovery, and disc conversion | verified | — | G001 |
| S002 | Game-native input and pointer architecture map | verified | S001 | G002 |
| S003 | Maintained PCSX2 fork and dependency stack build the current AVPE integration | partial | S001 | G001 |
| S004 | Default windowed and explicit headless launch paths boot the game | verified | S003 | G001 |
| S005 | Live control, memory, savestate, diagnostic input, and snapshot channel | verified | S004 | G001, G002 |
| S006 | Reproducible mission state and identified live rendered cursor | verified | S005 | G001, G002 |
| S007 | Reusable VM-thread EE-call shuttle | missing | S005, S006 | G002 |
| S008 | Native absolute pointer injection moves the rendered cursor | blocked | S007; issue #1 | G002 |
| S009 | Native mouse selection and command clicks | blocked | S007, S008 | G002 |
| S010 | Keyboard and mouse menu navigation through game-native paths | blocked | S007, S008 | G002 |
| S011 | Selector, camera, minimap, and pointer-mode integration | blocked | S008, S009 | G002 |
| S012 | Fresh-clone provisioning through the zero-argument launcher | missing | S003, S004 | G001 |
| S013 | End-to-end windowed product playable with native keyboard and mouse | blocked | S009, S010, S011, S012 | G001, G002 |

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

### S003 — current PCSX2 build: partial

Observed subset: the baseline emulator and the later AVPE control-channel fork
both produced the project PCSX2 executable with their required dependencies.

Gap: the current fork relationship is not reproducible from `deps.toml`:
`pcsx2.rev` names the upstream base, `fork_url` is empty, and the AVPE fork
revision exists only in a comment. The claim checker reports C001 as a coarse
file-change advisory, not as evidence that the build claim was falsified.

Evidence: claims C001 and C004; commits `6a94e4f` and `577042c`.

### S004 — launch paths: verified

Observed capability: zero arguments route to the windowed product, while the
explicit timeboxed headless path boots with no mapped window or audio output
and was subsequently used for the control-channel and mission/cursor evidence.

Evidence: commits `7fe135f`, `2f8a914`, and `fa6a65c`; claims C003–C006; and
[`re/headless.md`](re/headless.md).

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

### S007 — EE-call shuttle: missing, current focus

Required capability: a reusable fork-local module queues a call onto the VM
thread, sets the EE call context without corrupting guest state, returns through
a sentinel, reports failure loudly, and invokes `CRenderer::GetResolution` on a
real boot with plausible results.

Atomic work: issue #1.

### S008 — absolute cursor movement: blocked

Blocker: S007. Verification requires invoking
`Input_UpdatePositionAbsolute` on the live pointer and observing distinct
rendered positions for distinct injected coordinates in frame snapshots.

### S009 — mouse actions: blocked

Blockers: S007 and S008. Verification requires left press/release to drive
selection and right release to drive `CommandMove` through the game-native
handlers, with observed in-game effects.

### S010 — menu navigation: blocked

Blockers: S007 and S008. Verification requires keyboard and mouse to navigate
title and mission menus without using diagnostic pad injection as the shipping
implementation.

### S011 — selector and camera integration: blocked

Blockers: S008 and S009. Verification requires runtime evidence across selector
method changes, camera motion, minimap behavior, and pointer-mode transitions.

### S012 — fresh-clone launcher: missing

Missing capability: from a cold checkout with documented native dependencies,
`uv`, and user assets, `./run.sh` must provision portable dependencies/build
outputs and launch the windowed product without Ghidra or undocumented steps.

### S013 — playable native-input product: blocked

Blockers: S009–S012. Verification requires a clean windowed run through
representative menu, selection, movement-command, camera, and minimap
interactions using native keyboard and mouse input.
