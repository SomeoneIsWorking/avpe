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

**S024 — loading behavior and performance.** Representative native deliveries
match the ISO oracle byte-for-byte, and the grounded startup interval now has a
repeatable native-versus-optical timing differential. Work is proving failure
equivalence and explicit cold/warm state, exercising native I/O
recovery across guest reset and save-state load, and grounding a representative
mission transition. Current focus is attention, not a separate state.

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
| S012 | Fresh-clone provisioning through the zero-argument launcher | partial | S003, S004 | G001 |
| S013 | End-to-end windowed product playable with native PC RTS controls | blocked | S009, S010, S011, S012, S020 | G001, G002 |
| S014 | AVP:E save/load boundary and on-card data schema | partial | S001 | G003 |
| S015 | Atomic versioned PC-native save backend for AVP:E profiles and slots | blocked | S014 | G003 |
| S016 | Game save/load path operates without a virtual PS2 memory card | blocked | S014, S015 | G001, G003 |
| S017 | Existing AVP:E memory-card progress imports into native saves | blocked | S014, S015 | G003 |
| S018 | Desktop options are integrated into AVP:E's own menu system | missing | S010, S020 | G004 |
| S019 | Graphics, display, and resolution settings enumerate, apply, and persist | blocked | S018 | G004 |
| S020 | AVPE-owned host shell owns the visible window and presentation lifecycle | partial | S003, S004 | G001, G004 |
| S021 | AVP:E disc/file access boundary and asset namespace are mapped | partial | S001; issue #9 | G005 |
| S022 | User disc content provisions into a validated native asset store | verified | S021 | G001, G005 |
| S023 | Supported game asset requests use native host storage instead of emulated optical I/O | verified | S021, S022 | G001, G005 |
| S024 | Native asset I/O preserves behavior and measurably reduces loading time | partial | S023; issue #12 | G005 |
| S025 | AVP:E's required BIOS, kernel, and IOP service surface is inventoried | missing | S001, S004 | G006 |
| S026 | Clean-room AVP:E-specific HLE implements the required platform services | blocked | S025 | G006 |
| S027 | Supported target boots and runs without retail BIOS bytes | blocked | S026 | G001, G006 |
| S028 | HLE behavior is differentially verified against the BIOS-backed oracle | blocked | S025, S026 | G006 |
| S029 | Product prompts name PC keyboard and mouse actions instead of PS2 buttons | missing | S010 | G002, G004 |

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

Observed capability: `.gitmodules` names the maintained fork and the tracked
gitlink pins its exact revision; `deps.toml` records upstream provenance without
duplicating the pin. That revision builds the AVPE host, isolated control
runtime, and EE-call shuttle with Clang against the project dependency prefix.
The claim checker reports C001 as a coarse file-change advisory, not as
evidence that the earlier baseline-build claim was falsified.

Evidence: claims C001, C004, C007–C009 and C014–C015; project commit
`3f32427`; PCSX2 fork commit `e8d0317`; successful independent `avpe` and
`pcsx2-qt` Clang builds.

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
return PC. Pause Save activation replaced `0x012E85A0` with `0x015AFA70`, and
virtual cancel restored `0x012E85A0`.

The active menu-capable `GAvPPointer` is discovered by its validated virtual
capabilities rather than a concrete vtable address. Normalized pointer targets
`(0.7,0.3)` and `(0.7,0.4)` drove AVP:E's deferred `MenuCheck` hit-test and
focused Resume (`0x015DFB60`) and Save (`0x015E0640`) respectively. An invalid
coordinate returned 400 without changing deferred state. Pointer activation
then entered `0x015AFA70` through `GfsPointer::Input_Action`, with exact stack
restore. The product router maps arrows/WASD, Enter/Space,
Escape/Backspace, mouse motion, and primary/secondary edges to typed menu or
gameplay owners without DualShock emulation. All cited passing runs were
surfaceless, null-muted, and shut down gracefully.

Gap: real window key/mouse delivery remains unobserved because agent tests must
be windowless. Title, mission, and in-game menu coverage remains incomplete.
The prior Press START saved-state transition is no longer accepted as stable
evidence: the same deferred call later completed with exact restoration but
left menu `0x01346590` active through the 90-second deadline, falsifying C012's
broader claim. Pause-menu activation/cancel remains independently reproduced.

Evidence: claims C011 and C014, instruments I004–I005, issue #6,
`scratch/control-test/menu-proof.json`, and
`scratch/control-test/menu-pointer-proof.json` (ignored per-run artifacts).

### S011 — selector and camera integration: missing

Missing capability: runtime evidence is required across selector
method changes, camera motion, minimap behavior, and pointer-mode transitions.

### S012 — fresh-clone launcher: partial

Observed subset: `./run.sh provision` synchronizes and recursively initializes
the tracked PCSX2 fork and its nested dependencies, and `doctor` verifies the
checkout against the superproject gitlink. The project accepts GCC, Clang, or
AppleClang rather than encoding the agent's Clang verification policy.

Evidence: claim C013 and the provisioning tests in
`tests/test_dependencies.py`.

Gap: the zero-argument path does not yet provision the portable dependency
prefix or configure/build a missing product binary. A cold checkout therefore
still cannot reach the windowed product from documented native dependencies,
`uv`, and user assets without manual build steps.

### S013 — playable native-input product: blocked

Blockers: S009–S012 and S020. Verification requires a clean windowed run through
representative menu, click/drag selection, right-click contextual command,
keyboard-shortcut, camera, and minimap interactions using a coherent
StarCraft-informed PC RTS control scheme.

### S014 — save boundary and schema: partial

Observed subset: the `CProfile` create/load/save/delete/list boundary, card
namespace, multi-stage profile provisioning, 0x118-byte outer record, profile
payload placement, and compressed game-object stream are grounded from the
executable. The isolated control runner can now work on a copied formatted card
and report byte-level changes without exposing a window or mutating the source.

Gap: capture the live profile payload contract and map unknown record fields and
compressed data from at least two deliberately differing profiles and two game
saves. The exact high-level interception mechanism also remains unproven.

Evidence: claim C016 and [`re/save-path.md`](re/save-path.md). Atomic work:
issue #7.

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

### S018 — in-game native options surface: missing

Missing capability: AVP:E's own options menus do not expose project-owned
desktop graphics, display-mode, and resolution entries. Verification requires
opening the normal in-game options path, changing distinct supported settings,
rejecting an unsupported setting, navigating with keyboard and mouse, and
observing the persisted choices after a clean restart.

### S019 — native graphics and display settings: blocked

Blocker: S018. Verification requires enumerating supported modes, applying at
least two deliberately distinct resolution/display configurations through the
shipping PCSX2 setting owners, rejecting an unsupported choice, and observing
the selected configuration after a clean restart.

### S020 — AVPE host shell: partial

Observed subset: the standalone `avpe` executable links the PCSX2 emulation
core and AVPE-owned runtime, window, surface, settings, and input modules. Its
target has no PCSX2 `MainWindow`, display widget, game list, debugger, dialogs,
or settings UI. The default product launcher invokes this executable directly;
the Clang link and offscreen configuration check pass.

Gap: respecting the user's no-window test constraint means the real desktop
window has not been launched in this session. Runtime verification still must
exercise boot, resize, fullscreen, focus, close, and failure reporting. Atomic
work: issue #3.

### S021 — disc/file access boundary: partial

Observed subset: the `CZFile`/`CZRiffFile`/`CTbdFile` archive path, TBFF index,
uppercase-CRC lookup, loose fallback order, typed chunks, BWJ decompression,
and synchronous 1 MiB read loop are grounded statically. Both PCSX2 IOP
execution engines route `ioman`/`iomanX` imports through the same HLE boundary,
where an unclaimed request resumes the original IOP implementation. A real
surfaceless, null-muted boot observed 15 opens at that boundary, including the
loose TBX/TBD probes and two `TBF.TBF` opens; the absent sentinel produced zero
observations.

Gap: exercise representative mission-load namespaces and guest-visible failure
results before declaring the wider disc/file namespace complete.

Evidence: claim C017, instrument I007, issue #9, and
[`re/disc-io.md`](re/disc-io.md). Per-run detail is in the ignored
`scratch/control-test/native-assets-proof.json` artifact.

### S022 — native asset provisioning: verified

Observed capability: `avpe assets` extracts the user-supplied CHD into a scoped
staging directory, stream-converts its raw sectors, strictly traverses ISO9660,
validates exact `SYSTEM.CNF`, `SLUS_201.47`, and `TBD/TBF.TBF` identity anchors,
extracts and hashes every file, validates the finished manifest/store, and only
then atomically publishes `avpe-native-assets-v1`. The real supported disc
contained 268,924 MODE2 Form1 sectors and produced 137 files totaling
550,353,354 bytes. A second run fully revalidated and reused the store, and no
staging directory remained.

Wrong-disc ISO identity, wrong manifest identity, missing validated files,
malformed ISO endian fields, bad raw-sector sync, and a distinct Form2 layout
all produce explicit negative results through production validation paths.
All derived bytes remain under ignored `scratch/native-assets/`.

Evidence: claim C018, instrument I008, `src/avpe/native_assets.py`,
`src/avpe/iso9660.py`, `src/avpe/raw_sector.py`, and `tests/test_assets.py`.

### S023 — native asset reads: verified

Observed subset: the normal product launcher fully validates/provisions the
native store before passing its root and exact manifest SHA-256 admission token
to the core. `NativeAssetStore` rehashes that manifest, strictly indexes only
its safe case-insensitive members, canonicalizes each requested file below the
root, and verifies its declared size and SHA-256 before a first successful
claim. It revalidates content when size or modification time changes and
invalidates asset generations on unbind. `NativeAssets` separately title-gates
and normalizes read-only `TBD/`, `MOVIES/`, and `STREAMS/` paths, rejects writes,
traversal, missing members, and invalid stores, and leaves ELF/IRX bootstrap
unclaimed. `IopBios` uses a narrow cache-backed native descriptor adapter for
open/read/seek/close; it keeps per-descriptor cursor semantics without retaining
a host file descriptor.

Two surfaceless/null-muted native runs observed two TBF native opens,
41–56 host reads, 67,052–127,138 bytes, 2–4 seeks, and one close. The ELF and
every IRX open had zero native claims. Removing `AVPE_NATIVE_ASSET_ROOT` from
the same binary produced zero native claims for all 15 observed opens,
preserving the oracle. Live policy probes separately returned `native-file`,
`refused-access` for write and traversal, `refused-missing`, and `unhandled`
for bootstrap.

A clean-boot movie probe with an isolated formatted-card copy then completed
`MOVIES/EALOGO.PSS` through native storage: one open, 104 reads totaling its
exact validated 1,687,556-byte size, two seeks, and one close. Longer traces
also completed `FOXLOGO.PSS` and `ZONOLOGO.PSS` natively. The no-card negative
path entered `NOMEMLOGO.TBD` instead of laundering the missing precondition
into a movie success.

A clean-boot stream probe grounded the separate FSSOUND direct-CDVD boundary.
`STREAMS/MENU01.ZIV` received one native search/open, one seek, and two native
sector reads totaling exactly 49,152 bytes (24 2048-byte sectors). Synthetic
LSNs are scoped to validated VAG/ZIV files; ordinary CDVD calls stay unhandled.
The run was surfaceless and null-muted, shut down normally, and left the copied
formatted card byte-identical.

Runtime import-branch counters then showed zero original fallthrough for TBF,
all four startup movies, and `MENU01.ZIV`, while the bootstrap fell through.
The no-store opposite control recorded two TBF fallthroughs and zero native
claims. Claimed calls return directly to the guest before the original
IOP/CDVD implementation can schedule optical work.

Two further clean surfaceless/null-muted runs assembled canonical file-relative
chunks from the actual native ioman/cdvdman delivery paths and from PCSX2's
existing ISO reader. TBF, EALOGO, FOXLOGO, ZONOLOGO, INTRO, and MENU01 each
matched all 16 sampled 2048-byte chunks, for 96/96 exact SHA-256 matches with
identical ISO extents and file sizes. No trace record was dropped or conflicted.
A copied-digest OTHER-answer control was rejected at `TBF.TBF` offset zero,
and strict policy rejects source contamination and insufficient overlap.

The store-admission production tests separately exercise both outcomes for a
valid member and reject an unlisted member, wrong manifest admission digest,
unsafe and duplicate records, wrong-size content, same-size corrupt content,
content mutation after validation, exact-manifest mutation even with restored
timestamp, and generation change after unbind. A final surfaceless and
null-muted TBF run through fork `fd1978a` retained two native opens, 56 reads,
127,138 bytes, four seeks, one close, and zero original fallthrough while
bootstrap remained optical.

Evidence: claims C019–C023, instruments I009–I013,
`scratch/control-test/asset-byte-comparison.json` (ignored), and
[`re/disc-io.md`](re/disc-io.md).

### S024 — loading behavior and performance: partial

Observed subset: representative TBF, movie, and menu-stream native deliveries
match the PCSX2 ISO oracle across 96 canonical chunks, including identical file
sizes and extents. A separate trace-disabled timing instrument then measured
three alternating clean oracle/native pairs from the first `TBD/TBF.TBF` open
through the seek immediately following `STREAMS/MENU01.ZIV` search. All samples
used boundary ordinals 1→3 with zero EE-cycle, IOP-cycle, or frame spread.
Native medians reduced the interval from 40,408,849,912 to 35,312,223,239 EE
cycles (12.6126%), 5,051,106,429 to 4,414,027,549 IOP cycles (12.6127%), and
8,213 to 7,178 frames (12.6020%). Secondary host elapsed fell from
137.021072161 s to 120.172455308 s (12.2964%); within-mode host spreads were
1.344402630 s oracle and 1.624823501 s native.

The runs used project `edbfda4`, fork `87608f3`, one binary/disc/semantic-config
identity, actual optical/native backends matching their labels, surfaceless and
null-muted execution, disabled byte tracing, and isolated card copies whose
source and working SHA-256 remained identical. Copied ordinal-drift and
no-reduction controls were both rejected.

The runtime now fails store admission before a native claim when the exact
manifest, membership, size, or requested-file content identity is wrong. This
closes the previously observed arbitrary-directory and same-size corruption
gap, but it is not native/oracle guest-result equivalence.

The shipping ioman and synthetic-CDVD paths now share immutable 64 KiB cache
pages under an exact 512-page/32 MiB true-LRU bound. Cache fills coalesce at
most 16 pages through one transient host handle, failed/partial fills install
nothing, and generation changes invalidate all pages. Thirteen production C++
tests cover unaligned and multipage delivery, hit reuse, short read, EOF,
failed-fill retry, exact capacity/LRU eviction, explicit page drop, and store
generation change. A surfaceless/null-muted clean boot observed four fills,
54 hits, four resident pages (262,144 bytes), zero evictions, one peak transient
handle, and zero live handles after 53 native TBF reads; bootstrap remained
optical and native fallthrough stayed zero.

FSSOUND's native sector path now retains ownership of the immediate
`sceCdGetError` result instead of consulting unrelated optical-controller
state. A fixed-capacity one-shot token is keyed by the calling IOP stack. Six
production tests cover matching and wrong stacks, interleaving, replacement,
capacity rejection, and reset. The clean surfaceless/null-muted stream run
recorded two native MENU01 reads and exactly two matching completion
consumptions, with zero rejected records, zero active tokens, and unchanged
card bytes; unrelated calls still missed the token owner and used cdvdman's
original implementation.

Fresh post-landing captures on project `89cc05a` and fork `c0c6611` then
repeated the native/ISO differential through the shared cache: all 96 canonical
chunks across TBF, four startup movies, and MENU01 matched, the copied-digest
control was rejected at TBF offset zero, and both isolated card copies remained
byte-identical.

Guest reset clears synthetic mappings after descriptors close while retaining
the admitted store; shutdown and real disc-epoch changes close native
descriptors before unbinding the cache/store. Save-state version 1 serializes
exact native descriptor slots and identities plus synthetic LSN mappings and
fails closed if the admitted store cannot restore them. The combined Clang
build and lint pass; a pre-change v0 pause-menu state loaded successfully, and
a new v1 clean-boot state saved, reloaded, and returned to the same running
surfaceless/null-muted target. A live save/load with an active native descriptor
or mapping is still required before calling native-I/O recovery verified.

Gap: prove native and oracle missing, short-read, and injected-error results and
buffer effects; exercise explicit cold/warm cache protocols and live reset/
save-state recovery; and ground a representative mission transition. Failures
must never silently fall back. Evidence: claims C024 and C025, instruments I014
and I015, [`re/disc-io.md`](re/disc-io.md), ignored timing artifact
`scratch/control-test/load-timing/asset-load-timing-comparison.json`, and ignored
cache artifact `scratch/control-test/native-asset-cache-proof.json`, claims C026
and C027, and instruments I016 and I017. Atomic work: issue #12; resolved issue
#13 records the native CDVD completion seam.

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

### S029 — PC-native action prompts: missing

Missing capability: normal product menus and gameplay still present PS2 button
glyphs even though keyboard and mouse are the shipping controls. Verification
requires distinct menu and gameplay prompts to name their configured PC action
(`Esc — Back` at minimum), update when a binding changes, and contain no
PlayStation glyph fallback in the normal keyboard/mouse product path.
