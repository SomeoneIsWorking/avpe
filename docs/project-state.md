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

**S025 — required firmware service inventory.** The bounded BIOS census now has
repeatable clean-boot and post-savestate evidence plus grounded mission,
normal game-save, and normal game-load boundaries. The schema-v6 game-save
capture followed the
ordinary gameplay Pause → Save → empty-slot route through
`GSavePacifyMenu::Process` into `CProfile::SaveGame`, returned result zero, and
paired 3,396/3,396 EE BIOS calls plus 340/340 IOP oracle calls with zero pending
calls, sequence errors, or overflow. Result-bearing hot services retain bounded
first/last/min/max/change summaries instead of consuming the event capacity,
and unresolved oracle names are explicit `unknown` values. The runner also
waits for PCSX2's real post-savestate card reinsertion and post-write busy
lifecycle, so neither an ejected card nor an unflushed write can masquerade as
a title failure. The completed mission boundary remains valid with 2,638/2,638
initializer calls, 942/942 factory calls, and all 24 post-read rounds complete.
The latest clean mission archive capture isolates that same `CTbdFile::Load`
interval: it retained 103 event identities, paired 13,566/13,566 EE BIOS calls
and 543/544 IOP oracle calls with zero sequence errors or overflow; the sole
pending IOP call was live at the endpoint. Its deterministic inventory includes
the archive's ioman read/lseek, cdvd error, semaphore, SIF, audio, and thread
services without absorbing the post-load game-timer work.
The separate native `MOVIES/EALOGO.PSS` boundary begins only after its canonical
descriptor is admitted and completes after its matching handled `ioman.close`.
It retained 426 coalesced identities with zero overflow, including the movie's
ioman read/lseek/close activity and the reached libsd transfer services. Its
natural `TerminateThread` results range from `-1` to `3`, supplying one
observed service-level error result without inventing a synthetic failure.
The matching normal-load capture followed Pause → Load → populated slot → Yes,
crossed all three load-pacify calls and the exact `CProfile::LoadGame`
entry/return with result zero, completed the synchronous mission-goals modal,
and left the source card unchanged. The remaining work is the shutdown,
service-level negative-path inventory, plus required runtime operations outside
the current boot, archive, save, and load slices.
Static IRX analysis now narrows the IOP candidate surface to seven retained
modules, 61 import tables, 260 import stubs, and 19 library identities; it is
explicitly not runtime coverage.
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
| S011 | Selector, camera, minimap, and pointer-mode integration | partial | S008, S009; issue #19 | G002 |
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
| S024 | Native asset I/O preserves behavior and measurably reduces loading time | verified | S023 | G005 |
| S025 | AVP:E's required BIOS, kernel, and IOP service surface is inventoried | partial | S001, S004; issue #20 | G006 |
| S026 | Clean-room AVP:E-specific HLE implements the required platform services | blocked | S025 | G006 |
| S027 | Supported target boots and runs without retail BIOS bytes | blocked | S026 | G001, G006 |
| S028 | HLE behavior is differentially verified against the BIOS-backed oracle | blocked | S025, S026 | G006 |
| S029 | Product prompts name PC keyboard and mouse actions instead of PS2 buttons | missing | S010 | G002, G004 |
| S030 | Hosted redistributable build and verification matrix | partial | S003, S012 | G001 |

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
through the game handle table. It also validates the synchronous mission-goals
load modal by its singleton and vtable, traverses its bounded object tree to the
unique grounded Exit item, invokes that item's exact virtual focus handler, and
activates it synchronously through `GMenu::Input`. Returning directional calls
changed pause-menu focus from Resume (`0x015DFB60`) to Save (`0x015E0640`).
Ordinary activation and cancel queue deferred guest calls through the VM
scheduler; the reentrant mission-load activation is synchronous because its
modal-loop observation PC can otherwise masquerade as a deferred return. Both
forms restore interrupted EE/FPU/VU0 context plus exact reserved stack bytes.
Pause Save activation replaced `0x012E85A0` with `0x015AFA70`, virtual cancel
restored `0x012E85A0`, and the clean mission modal cleared its singleton before
the grounded load return.

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

The direct absolute-motion contract is limited to the pause path: on the Save
Game menu its complete guest routine reaches `SleepThread` and BIOS `EENULL`
instead of the shuttle return boundary. `NativeInputDispatch` now observes the
real `GInputDevice::Process` member-call seam and proved its game-owned input
buffer and neutral menu callback, while separately identifying the registered
virtual pointer callback. Its diagnostic single-event queue replaces exactly
that callback's game-owned data and descriptor. The callback itself executes
its virtual `MenuCheck` twice (derived and base pointer routines); a
post-return third check was removed as redundant. A Save Game probe proved
pointer movement and activation on that ordinary callback path. Its measured
`GMenuButton` center `(280,378)` focused `0x015AFD10`; the original pointer
action then completed through the deferred scheduler with exact stack
restoration. The former target `(431.33,178.80)` intersects only a `GMiner`
rectangle and correctly clears focus. `HostInputRouter` now uses the grounded
dispatch-bound movement path for every discovered menu; real-window delivery
remains unverified (issue #6).

Gap: real window key/mouse delivery remains unobserved because agent tests must
be windowless. Title and broader in-game menu coverage remains incomplete.
The prior Press START saved-state transition is no longer accepted as stable
evidence: the same deferred call later completed with exact restoration but
left menu `0x01346590` active through the 90-second deadline, falsifying C012's
broader claim. Pause-menu activation/cancel remains independently reproduced.

Evidence: claims C011 and C014, instruments I004–I005, issue #6,
`scratch/control-test/menu-proof.json`, and
`scratch/control-test/menu-pointer-proof.json` (ignored per-run artifacts).

### S011 — selector and camera integration: partial

Observed subset: `NativeCameraInput` invokes AVP:E's original
`Input_GPMove(0x001af140)`, `Input_GPRotate(0x001af240)`, and
`Input_GPZoom(0x001af480)` callbacks through the EE shuttle using the grounded
eight-byte float-pair `CInputData` prefix. A clean `mission1.p2s` surfaceless,
null-muted run proved that move changed camera `+0x158/+0x15c` to `[25,0]` and
retained pointer input type `1`; zoom entered minimap mode and produced a
bounded cursor/camera-pointer state; rotate changed the minimap cursor and
camera pointer. Each call reported exact stack restoration and nonzero EE
cycles, with stable camera, pointer, and minimap singleton identities.

The standalone host maps held W/A/S/D and arrow keys through a 16 ms camera
tick and maps the mouse wheel to the same game-native zoom callback. The
surfaceless control route `POST /input/camera` and its acceptance policy
exercise the native owner, but the real window event delivery remains
unobserved under the no-window agent-test constraint.

Gap: pointer-mode changes
after menu selection and a user-visible windowed camera/minimap interaction
remain required before S011 is verified.

Evidence: claim C030, resolved issue #19, and
`scratch/control-test/native-camera-proof.json` (ignored per-run artifact).

### S012 — fresh-clone launcher: partial

Observed subset: the default launcher and `./run.sh prepare` verify and
recursively initialize the tracked PCSX2 fork, then configure and build the
current standalone `avpe` target. An existing binary no longer bypasses the
CMake build: a configured tree is incrementally rebuilt, while a missing build
tree is configured first. The launcher now has a guarded path to provision the
project-owned `build/deps`
Qt/dependency prefix through the tracked PCSX2 workflow when it is absent. The
project accepts GCC, Clang, or AppleClang rather than encoding the agent's
Clang verification policy.

Evidence: claim C013, the provisioning tests in `tests/test_dependencies.py`,
the preparation tests in `tests/test_build.py`, and a successful real
missing-prefix `avpe prepare` on Linux that rebuilt the complete multi-library
dependency stack and standalone product under `build/` with Clang 22.1.8.

Gap: that Linux run reused checksum-validated source archives already present
in the checkout, so fresh-clone downloads remain unverified. The complete cold
path also remains to be verified on every other supported host platform.

### S013 — playable native-input product: blocked

Blockers: S009–S012 and S020. Verification requires a clean windowed run through
representative menu, click/drag selection, right-click contextual command,
keyboard-shortcut, camera, and minimap interactions using a coherent
StarCraft-informed PC RTS control scheme.

### S030 — hosted redistributable verification: partial

Observed subset: `.github/workflows/verify.yml` defines cold, asset-free Linux
and Intel macOS jobs. Both build through `src/avpe/ci.py`, which composes the
shipping `prepare_product()` owner with the normal `tools/verify.py` gate;
the workflow does not upload game data, derived game data, or a runtime cache.
Its bootstrap action revisions and the `uv` wheel hashes are pinned. Windows is
currently inapplicable because `dependency_prefix.select_workflow()` has no
Windows implementation, so the product cannot provision or build its declared
target there. Apple Silicon remains unqualified.

Gap: obtain successful hosted runs on both declared hosts, add an asset-free
installable package assertion, and implement/qualify the missing Windows and
Apple-Silicon host paths before claiming a complete desktop release matrix.

Evidence: the version-controlled hosted-verification owner, workflow, and
focused `tests/test_ci.py` policy tests. Hosted execution evidence is pending.

### S014 — save boundary and schema: partial

Observed subset: the `CProfile` create/load/save/delete/list boundary, card
namespace, multi-stage profile provisioning, 0x118-byte outer record, live
`SetGameData` pointer/size/revision/slot-count contract, profile payload
placement, BWJ mode/word-token decoding, and the fixed game-save stream prefix
are grounded from the executable and a BIOS-backed paused state. The isolated
control runner can now work on a copied formatted card and report byte-level
changes without exposing a window or mutating the source.

Gap: map unknown record fields and the decompressed object/class and gameplay
meaning of at least two deliberately differing profiles and two game saves,
and implement the native interception. Two
normal Save Game menu runs now produced separate slot-0 and slot-1 records with
different serialized bodies on isolated card copies. The BWJ decoder reaches
the fixed prefix and the same object-header structure in both records: 189
top-level starts, 1,073 nested starts, 1,262 nested end records, maximum depth
3, and 67 distinct opaque class IDs with identical histograms. It rejects
truncated headers and unbalanced object ends through the production parser, but
does not decode editable fields. A direct diagnostic call is not a substitute
because it exceeded the shuttle budget while driving synchronous card
services. The exact high-level interception mechanism is still narrowed to the
`CProfile` operation boundary and its `CShell`/save-menu callers, but remains
unproven in a native implementation.

The `GObject::Save`/`Load` decompilation additionally establishes that object
bodies are class-descriptor driven: scalar fields are emitted at descriptor
widths, while pointer and pointer-array kinds carry saved-object identities.
The 16-byte object headers are therefore not enough to decode editable fields;
the 67 observed class IDs require descriptor extraction before a native writer
can preserve the loader contract. A BIOS-backed live probe now resolves all 67
IDs to 6,304 descriptor fields and the production splitter validates their
scalar/pointer wire boundaries. `SaveAll` emits each root's complete recursive
structure before its handle-ordered class-specific virtual `SaveEx` queue.
Live parent-chain evidence maps the 67 observed classes to six selected
implementations (`GObject`, `GUnit`, `GObjectAI`, `GPlayerManager`, `GDropShip`,
and `GFOWSaver`). Bounded readers and the production recursive parser now
consume the selected payload layouts, the live fixed-size message table and
dynamic message-size fallback, and the grounded player-manager active-state
predicate; both retained records parse through their exact top-level
terminators. A matching BIOS-backed load run then selected the produced slot 0
through the normal Pause → Load path, crossed all three
`GLoadPacifyMenu::Process` calls, returned zero from `CProfile::LoadGame`, and
completed the synchronous mission-goals modal through its exact registered
Exit action while preserving the source card. Editable field meanings and
native interception remain open.

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
the Clang link and offscreen configuration check pass. Its settings owner now
supplies the bundled Roboto text font before GS startup, rather than leaving
`ImGuiManager` with an empty font list; a normal launcher run consequently
kept the standalone process alive through GS CRTC setup and multiple game FMVs
instead of failing during render-device creation. Native surface acquisition
now rejects an engaged `WindowInfo` whose required display or window handle is
null, with three no-window C++ tests covering Surfaceless, X11/Wayland, Win32,
and MacOS validity.

Gap: the desktop-control provider cannot enumerate this Qt window, so the
launcher evidence proves renderer/game bootstrap but not visible ownership or
event delivery. Runtime verification still must exercise boot, resize,
fullscreen, focus, close, and failure reporting on a controllable desktop.
Atomic work: issue #3.

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

### S024 — loading behavior and performance: verified

Observed subset: representative TBF, movie, and menu-stream native deliveries
match the PCSX2 ISO oracle across 96 canonical chunks, including identical file
sizes and extents. A separate trace-disabled timing instrument then measured
three alternating clean oracle/native pairs from the first `TBD/TBF.TBF` open
through the seek immediately following `STREAMS/MENU01.ZIV` search. All samples
used boundary ordinals 1→3 with zero EE-cycle, IOP-cycle, or frame spread.
Native medians reduced the interval from 40,408,849,912 to 35,312,223,239 EE
cycles (12.6126%), 5,051,106,429 to 4,414,027,549 IOP cycles (12.6127%), and
8,213 to 7,178 frames (12.6020%). Secondary host elapsed fell from
137.021072161 s to 120.172455308 s (12.3688%); within-mode host spreads were
1.344402630 s oracle and 1.624823501 s native.

The runs used project `8fcf8d1`, fork `e8c7af9`, one binary/disc/semantic-config
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
surfaceless/null-muted target.

Two separate clean runtime falsifiers now cover the live state. The ioman run
saved `INTRO.PSS` at guest fd 257 and cursor 131,072, restored the identical
descriptor set, then advanced from 147,456 to 393,216 observed bytes without a
reopen or optical fallback. The CDVD run restored `MENU01.ZIV` at synthetic LSN
3,758,096,384 with exact size 7,602,176, SHA-256, and next-LSN 3,758,100,096;
post-load reads advanced from 65,536 to 131,072 observed bytes while matching
completion consumption advanced from three to four. Both save/load snapshots
had zero active completion tokens, both processes reported surfaceless and
null-muted Running state, and both isolated source/working card hashes remained
byte-identical. Snapshot-drift, reopen, and active-token OTHER-answer controls
are rejected by the proof policy. Strengthened reruns also required explicit
post-load Running/surfaceless/null-muted status and valid bounded-cache
snapshots with zero transient host handles; the CDVD leg exercised the exact
512-page/32 MiB resident bound and eviction path.

The clean-boot M1 transition trigger is now verified: after native
`MENU01.ZIV` readiness, `SetNextLevel` staged/restored the exact
`M01/background.tbd` path and the real loader populated `pThe GAvPWorld`; the
native leg advanced TBF reads with zero original fallback and retained the
bounded cache. Grounded disassembly places the `CTbdFile::Load` continuation at
`0x0016FA4C`. The recompiler observer first proved that all 124 payload
`ReadChunk` calls complete in a 1.164733261 s/67-frame burst with 4,029,554
bytes and no loader error, then localized the wait to the outer `InitTypes`
call. Stack-aware initializer and object-factory observations identified
`CPresetFillData` and `GExitMissionGoalsButton::Create`; static and runtime
evidence then grounded a synchronous `GMissionGoalsMenu` load modal, not
unfinished storage work. The native mission probe now waits until the exact
Exit object exists, focuses it through its title virtual, invokes
`GMenu::Input(Activate)` synchronously, and clears the modal. Clean oracle and
native runs reached `0x0016FA4C` with all 24 post-read rounds, 2,638/2,638
initializer calls, 942/942 factory calls, and zero sequence errors. Three
alternating clean oracle/native mission pairs then passed the timing comparator
at stable `1→2` boundary ordinals: oracle medians were 1,799,787,694 EE cycles,
224,973,420 IOP cycles, and 366 frames; native medians were 461,714,639 EE
cycles, 57,714,287 IOP cycles, and 94 frames. The reductions were 74.35% for
EE/IOP cycles and 74.32% for frames; the ordinal-drift and no-reduction
controls rejected their mutations.

The schema-v2 rerun on project `f9cab93` and fork `c0e8b29` closes the
remaining interval-wide exclusion. Three alternating clean oracle/native pairs
again passed at stable `1→2` ordinals. Oracle medians were 1,801,962,393 EE
cycles, 225,245,258 IOP cycles, 367 frames, and 6.106907048 s host elapsed;
native medians were 462,041,820 EE cycles, 57,755,201 IOP cycles, 94 frames,
and 1.554046820 s host elapsed. This is a 74.36% EE/IOP reduction, 74.39%
frame reduction, and 74.55% host-time reduction.

Every oracle interval positively exercised optical delivery: each delivered
1,985 sectors, scheduled 1,985 read waits, and scheduled 2,852–2,854
sector-ready waits. Every native interval recorded zero action, read, and
sector-ready waits and zero sector deliveries. The native transition policy
also observed zero dropped paths and no increase in original fallback for any
TBD, movie, or stream path. All six run envelopes had zero errors, used one
binary/disc/config identity, remained surfaceless and null-muted with byte
tracing disabled, and preserved identical source/working card hashes. The
copied ordinal-drift and no-reduction controls were rejected.

Title-observed failure tracing remains separate hardening in issue #16; it does
not substitute for this verified loading capability. Live guest reset cleanup
is verified in issue #15. Evidence: claims C024 through C029 and C038,
instruments I014 through I019, [`re/disc-io.md`](re/disc-io.md), ignored
timing artifact
`scratch/control-test/mission-load-timing/mission-load-timing-comparison.json`,
ignored cache artifact
`scratch/control-test/native-asset-cache-proof.json`, and ignored transition
artifact
`scratch/control-test/native-marine-m1-transition-proof.json`. Resolved issues
#12–#15 record the full-interval timing, native CDVD completion, live
state-recovery, and guest-reset cleanup seams.

### S025 — required firmware service inventory: partial

Observed subset: the BIOS-backed IOP import boundary now emits a bounded,
sequence-ordered v6 diagnostic census containing each reached import's module,
ordinal, resolved name (or `unknown` when unresolved), first four input
arguments, handler availability, actual outcome, and occurrence count. A
handled HLE call carries
its grounded signed `v0` result. An oracle fallback records its exact stack and
caller return PC, then emits a separate paired return event with the eventual
signed `v0`. The same census records shared EE `SYSCALL` dispatches with their
normalized number, BIOS name, four argument registers, and whether the call
returned directly from PCSX2 or continued into the BIOS. Return-capable BIOS
calls pair by stack pointer and exact post-syscall PC, retaining bounded nested
calls with the same stack pointer until their exact return boundary. ABI disposition is
independent of ownership: supported 32-bit results carry signed `v0`, declared
64-bit results carry the full unsigned `v0` as `result_u64`, void and
non-returning calls carry none, and unknown results remain explicitly
unobserved. The census also records loadcore module registration/release,
intrman interrupt registration, and sifcmd RPC registration. EE and IOP
exception-entry boundaries also record the domain, cause code, pre-entry PC,
and branch-delay state without changing dispatch or fallback behavior. EE and
IOP counter target/overflow paths also record counter state, cycle, and whether
the interrupt was delivered. The isolated C++ and Python tests prove disabled
capture, ordering, outcome/result-validity pairs, rejection of legacy or
malformed result fields, exception/timer fields, and the exact capacity/
overflow behavior, wrong return pairing, malformed result dispositions, and
bounded aggregation of continuously changing results.

A successful `Host::OnSaveStateLoaded()` reset now separates post-savestate
execution from restore-time scheduler traffic. Three different BIOS-backed
savestate resumes produced ordered traces of 220, 251, and 71 events
respectively, all with zero overflow; their event mixes differ (Zono-splash
`title-real`:
EE syscalls/exceptions, `pause-menu`: EE syscalls/exceptions/timers,
`mission1`: EE exceptions/timers).

The phase runner can clear and re-enable the sink at a later control boundary.
A pause-menu `down` action and an isolated save-then-load sequence both
complete with zero-overflow `statefile_to_menu` and
`save_load_to_menu_action` traces. The menu action completed synchronously in
this state, while the probe also accepts deferred completion used by other menu
owners. Capture runs on the emulation CPU thread: two menu runs each produced
7 events (2 EE syscalls and 5 exceptions). The save-load phase now waits for
the restored game's exact `down` action and snapshots immediately when it
completes, instead of waiting for next VSync. Two pause-menu repeats retained
the same 28 event identities, five fully paired EE BIOS calls, and zero
overflow. This proves the narrow restored-menu boundary, not archive
serialization internals or shutdown.

Two fresh `mission1.p2s` statefile-to-running captures further exposed the
remaining boundary defect: one had 237 events and its immediate repeat had one
timer event. Both were bounded valid traces, so the result is a negative
repeatability control rather than mission-service coverage.

The title/profile phase advances the Zono splash through Start, waits for both
the live focused title menu and initialized guest pad, and sends one physical
activation. It observes the ordered title/profile entries, waits through their
temporary registry overlap, then activates the settled profile menu. The
current probe passes through `GProfileMenu` into `GLoadProfileMenu`; its bounded
census and the repaired initialization race are recorded in
[issue #7](issues/0007-profile-creation-fails-before-gameplay.md).
This is a profile-list service slice, not profile persistence or normal game
load evidence. Earlier deferred-title captures retained 150 versus 51 events
and remain a negative repeatability control, not complete title coverage.

`tools/analyze_bios_traces.py` now turns retained v6 captures into a
deterministic inventory report using the same strict trace validator as the
runner. Its v5 inventory summary separates observed results, returned oracle calls,
returned void calls, unobserved results, and non-returning transfers. The
earlier seven-capture v1
set still proves
its phase boundaries and event identities, but its sampled `v0` fields were
pre-dispatch values and are rejected by the current analyzer; its claimed
service results are withdrawn.

A fresh Clang-built clean-boot native stream probe also captured the BIOS
census after the verified `Running` boundary. It retained 1,290 bounded event
identities with zero overflow, including 11 recognized IOP import identities
(`ioman.read`, `cdvdman.sceCdRead`, `sceCdSeek`, `sceCdGetError`, and
`sceCdSearchFile` among them) with occurrence counts. The same run completed
the native `MENU01.ZIV` proof with two sector reads and two consumed CDVD
completion records. Imports without an HLE or debug handler are now retained
as unresolved oracle observations, but this clean boot encountered none; the
zero count is therefore a measured negative rather than an instrumentation
blind spot.

The mission BIOS phase waits for native `MENU01.ZIV` readiness and arms a
one-shot shared-EE observer around `CShell::ShellLoadLevel` entry `0x0016F910`
and continuation `0x0016FA4C` on the emulation CPU thread. Its exact loader,
chunk, nested `LoadCore`, type-initializer, and object-factory observations are
bounded and stack-paired. They identified the last outer initializer as
`CPresetFillData` and its active factory as `GExitMissionGoalsButton::Create`.
Static RE then showed the constructor synchronously enters
`GMissionGoalsMenu::LoadHackCallback`, whose tight loop polls `GInputDevice`
before normal callback registration. `NativeHostYield` pumps only pending host
CPU transactions at that exact title loop; `NativeMenuInput` waits for the
grounded Exit object, focuses it through its exact virtual, and invokes
`GMenu::Input(Activate)` synchronously. Deferred execution is deliberately not
used there because the request originates reentrantly at the same PC and could
falsely complete on the original guest block.

A valid clean native run then reached the exact continuation with no loader
error: 134/134 observed chunks and 124 payload chunks completed, all 24
post-read rounds returned, 2,638 initializer calls paired with 2,638 returns,
and 942 factory calls paired with 942 returns. The mission, post-read,
initializer, and factory sequence counters were zero. The older single-active-
frame load-timing observer reported 10 sequence errors because nested
`ReadChunk` calls are not modeled by that timing frame; those timing totals are
not evidence for this mission path. The exact Exit object was focused and
activated in 3,609 EE cycles with stack restoration, and the mission-goals
singleton became zero.

Two clean v3 captures then completed that same mission boundary and paired
13,566/13,566 and 13,565/13,565 return-capable BIOS entries/returns with zero
pending calls, sequence errors, or overflow. Both repeat the same 11 syscall
identity/disposition classes. `ResumeIntrDispatch` is non-returning;
`FlushCache` and `sceSifSetDChain` return control but are void; the observed
thread/semaphore and SIF DMA services return declared 32-bit values. Fixed
thread/semaphore result sets repeated. Hot totals did not: `sceSifSetDma`
differed by one call and direct `FlushCache` by two, so exact syscall totals and
SIF transaction IDs are not a repeatability contract. The v2 captures remain
entry/import identity evidence only; C034 and I020 are falsified/distrusted.

Two clean v4 captures supersede the remaining IOP result gap. Both completed
the same grounded mission boundary and repeated the same import and syscall
identity sets. They paired 527/527 IOP oracle entries/returns with zero pending
calls or overflow; `cdvdman.sceCdGetError` returned grounded result 0 on all
527 calls at stack `0x001FA510` and caller PC `0x0003CB2C`. Both traces paired
13,565/13,565 EE BIOS entries/returns with zero pending calls, sequence errors,
or overflow. The first trace retained 1,358 event identities and the current
relinked repeat 1,353,
so exact hot-path event totals remain outside the repeatability contract.

A schema-v6 BIOS-backed run from `mission1-current.p2s` and the matching
isolated `after-slot0.ps2` card completed the ordinary gameplay Pause → Save →
empty-slot path. It observed all three `GSavePacifyMenu::Process` calls, entered
`CProfile::SaveGame` at `0x00130170`, returned at `0x00130374` with result zero,
and changed the working card while preserving the source card. The trace
retained 121 event identities, paired 3,396/3,396 return-capable EE BIOS calls
and 340/340 IOP oracle calls, and reported zero pending calls, sequence errors,
or overflow. The IOP slice contains 117 `cdvdman` ordinal-51 returns, 111
`sifcmd.sceSifGetOtherData` returns, 111 `mcman` ordinal-9 returns, and one
`mcman` ordinal-10 return. The stripped `mcman` names are recorded as
`unknown`, not empty strings. Its changing ordinal-9 results are retained as a
bounded summary (`min=4`, `max=8192`, 92 changes) rather than one event per
result. PCSX2's 60-frame savestate card auto-eject and 300-frame post-write
busy intervals are both observed and awaited through the production
`/memory-card/state` route.

A matching schema-v6 load run from `mission1.p2s` and the produced
`after-slot0.ps2` card completed the normal Pause → Load → populated slot →
Yes route. It observed all three `GLoadPacifyMenu::Process` calls, entered
`CProfile::LoadGame` at `0x00130000`, and returned at `0x00130168` with result
zero. The load then reached the synchronous mission-goals modal; its exact
registered Exit action completed in 3,609 EE cycles with stack restoration.
The trace retained 349 event identities, paired 14,444/14,444 return-capable
EE BIOS calls, and captured 16,357 IOP oracle entries with 16,356 returns. The
one pending IOP call is the blocking `thmsgbx.ReceiveMbx` at the chosen guest
boundary, not an overflow or pairing error. The inventory contains 17 EE
syscall and 86 IOP import identity/result summaries across the load and resumed
mission initialization, so it is a complete operation boundary but not yet an
archive-only service slice.

Gap: extend the restored-menu completion pattern to stable title completion and
add a grounded shutdown phase boundary.
EE timers, remaining interrupt delivery, kernel primitives outside the mission
slice, executable loading, IOP module loads and services outside the recognized
import surface, and additional service-level negative-path semantics remain
incomplete;
S025 cannot become verified from this mission census alone.
The static IRX scan separately found seven extracted module headers, 61 library
tables, 260 import stubs, and 19 library identities. Six modules are stripped,
so 219 entries have no symbol name and remain library/ordinal candidates.
The retained legacy cold-boot trace adds 60 module-registration events across
30 names and 38 name/version pairs, but is schema v1 and does not provide
current result evidence; registration is not proof of import execution.
Static presence and registration do not close the remaining service and
negative-path inventory.

Evidence: claims C035–C037, C039, and C040, instruments I021–I025,
[`re/bios.md`](re/bios.md), issue #20,
the `NativeBiosTraceTest` production tests, and ignored repeated artifacts
`scratch/control-test/bios-mission-service-v4.prev.json` and
`scratch/control-test/bios-mission-service-v4.json`, plus
`scratch/control-test/game-save-bios.json` and its deterministic inventory.
The normal-load evidence is `scratch/control-test/game-load-bios.json` and its
deterministic inventory.
The native-movie evidence is
`scratch/control-test/bios-trace-movie.json`; a deliberately unbounded boot
capture overflowed and is negative evidence for using a broad phase rather than
the native descriptor lifecycle as this operation's boundary.
Claims C031/C034 are falsified
and I020 is distrusted; none is current result evidence. Three repeated
surfaceless clean boots
also captured the same 28-event `clean_boot_to_running` trace with zero
overflow through the atomic production capture route; three restored-state
captures were also accepted with zero overflow after the post-restore reset.

Static candidate evidence now complements the runtime census: the bounded
`tools/analyze_ee_syscalls.py` scanner found one executable segment in the
user-supplied target ELF, 158 BIOS wrapper definitions, 458 direct wrapper
callsites, 8 direct syscall instructions, and 63 candidate syscall numbers.
This does not prove execution, indirect dispatch, or service results. The
clean-boot asset-open boundary now separately proves one normal `GsPutIMR`
return with `result_u64=0x000000000000ff00`, with zero EE pairing errors after
the nested pending-call fix. Ghidra reaches `GsGetIMR` only through
`ps2_screen_capture_GetImage`; its sole input-poller caller is guarded by
poll index one even though `CPS2Input::PollDevices` executes only index zero,
so that helper is outside the normal-title inventory. The grounded mission
return is now available for a stable service slice; the early world pointer
and generic frame boundary remain insufficient substitutes for other phases.

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
