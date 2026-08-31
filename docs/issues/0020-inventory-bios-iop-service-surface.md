---
id: 20
title: Inventory AVP:E BIOS and IOP service surface
status: investigating
symptom: The AVP:E-specific BIOS/HLE service surface is not yet inventoried
state_items: S025,S026,S027,S028
tags: bios,hle,iop,inventory,re
created: 2026-08-28
updated: 2026-08-31
---

## Root cause

The project began with only selected asset-import/debug hooks and no bounded
firmware census. The remaining root gap is now narrower: the v5 mission census
has grounded EE BIOS and IOP oracle return owners with ABI-aware result
validity, each confirmed by repeated mission evidence. Schema v5 now captures
declared 64-bit EE results without truncation, but a live title exercise of
those GS calls, stable guest-owned save/load and shutdown boundaries, and
service negative paths are still absent. One mission slice cannot substitute
for the complete required firmware contract.

## Current work

`NativeBiosTrace` v5 retains the v3 EE `SYSCALL` contract through the shared
interpreter implementation, including their four argument registers and
whether PCSX2 returned directly or dispatched into the BIOS. Return-capable
BIOS entries pair by guest stack pointer and exact post-syscall PC. A ps2sdk-
grounded disposition table separates captured signed 32-bit results, returned
void calls, unobserved result types, and non-returning context/process/thread
transfers. Recognized HLE/debug IOP imports snapshot arguments, stack pointer,
and caller return PC before dispatch. Handled HLE carries its immediate result.
Oracle fallback queues a bounded frame, registers that exact caller return
block, and pairs the eventual signed `v0` by stack pointer and return PC through
`NativeIopExecutionHooks`. The recompiler instruments only registered return
blocks; the interpreter scans the registry only while an oracle call is pending.
The census also records EE/IOP exception entry,
loadcore module registration and release, interrupt registration, and SIF RPC
registration. EE and IOP counter target/overflow paths now record the counter
state, cycle, and whether the interrupt was delivered. All observations use
narrow calls at the existing owners, remain observation-only, and are exposed at
`GET /bios/trace` for control-test diagnostics. Repeated import, syscall,
exception, and timer identities are coalesced with occurrence counts; unknown
import-looking probes remain on the original oracle path.

The surfaceless runner now captures the sink atomically at the verified
`Running` boundary through `POST /bios/trace/capture`. Three repeated clean
boots produced the same 28-event slice (20 module registrations, 7 IOP
exceptions, 1 IOP timer event, zero overflow), proving the boot boundary is
repeatable. The capture is deliberately labelled `clean_boot_to_running`; it
does not claim to cover later EE or game-service activity.

Successful savestate restoration is now an explicit phase boundary: the
standalone frontend resets the sink from `Host::OnSaveStateLoaded()` before the
emulation thread enters `Running`. The Zono-splash `title-real.p2s`, `pause-menu.p2s`, and
`mission1.p2s` resumes produced 220, 251, and 71 ordered events respectively,
all with zero overflow and different event mixes. This proves the bounded
instrument can observe post-restore execution without retaining the high-rate
restore-time scheduler burst.

The phase runner now has a reset/start boundary. A pause-menu `menu_down`
capture accepted the game's synchronous native action, and capture is aligned
to the emulation CPU thread. Two identical menu runs each produced 7 ordered
events (2 EE syscalls and 5 exceptions), with zero overflow. The save-load
phase now loads the requested state, executes that same restored menu's exact
`down` action, waits for its completion, and snapshots immediately on the CPU
thread. Two pause-menu repeats retained the same 28 event identities, five
fully paired EE BIOS calls, and zero overflow. The save archive itself remains
a control-boundary observation rather than an invented BIOS event claim.

Phase capture now has a narrower boundary: the control route can arm the sink
and wait for the next `Counters::VSyncStart` transition on the emulation CPU
thread. Two repeated pause-menu captures through that route remained bounded
with zero overflow but retained 21 and 11 event identities, with different
exception/syscall identity sets. This removes the control request's frame
position race, but the differing traces show that a frame transition alone is
not a completion condition. The restored menu-action boundary now covers the
pause-menu slice; title and mission restore states still need their own
guest-owned completion evidence.

### Finding (2026-08-31, Zono-splash boundary discriminator)

Despite its filename, `title-real.p2s` resumes on the Zono splash: its
screenshot contains the Zono logo and the live `GVideoPlayer` singleton is
present. It reached verified surfaceless `Running` but rejected the typed native
`down` action with HTTP 409 because no game menu owned navigation callbacks.
It therefore cannot supply a title-menu completion boundary. That probe needs
an independently grounded title-owned transition; a host delay, VSync edge, or
synthetic menu callback would not establish one.

### Finding (2026-08-31, title activation repeatability control)

The phase runner now presses Start through the diagnostic controller seam,
waits for a live callback-registry menu, starts a fresh sink, activates that
title menu through `NativeMenuInput`, waits for the deferred call, and captures
on the CPU thread. Two runs reached the same phase and operation with zero
overflow, but the first retained 150 events with 524/524 paired EE calls and
51/51 paired IOP oracle calls while the second retained 51 events with 15/15
paired EE calls and no IOP calls. Title activation is a grounded transition but
not yet a repeatable service completion boundary; a later title-owned state
signal is required.

### Finding (2026-08-31, game-save fixture discriminator)

`NativeGameSaveBoundary` now scopes the census from the validated live
`CProfile::SaveGame` entry `0x00130170` to its final `jr ra` at `0x00130374`,
capturing its signed `v0` before control returns to the caller. It disables the
general control-test trace until that exact entry, so a failure cannot be
misreported as menu or resumed execution traffic. The available
`save-menu.p2s` did not enter `CProfile::SaveGame` or change its isolated card
after dispatch-bound pointer activation or title Cross input; generic native
`down` left its focus empty. This is a fixture/input-path discriminator, not
save evidence: the normal `GSavePacifyMenu::Process` path still needs a
guest-owned state fixture.

Pairing the historical `mission1-current.p2s` with `after-slot0.ps2` is also
not that fixture. The restored screen entered the title's load-failure and
load-confirmation dialogs; its menu transitions never reached the grounded
observer, whose bounded capture remained empty. A 128-byte card delta from one
traversal is metadata activity, not evidence of `CProfile::SaveGame`. Future
game-save probes require a state/card pair that restores the same live profile
and mission rather than treating independently captured artifacts as
interchangeable.

### Finding (2026-08-31, normal game-save owner)

`GSavePacifyMenu::Process` at `0x00202F40` increments its process counter and
only on its third pass calls `CShell::SaveGame` at `0x0016FAE0`; that routine's
call at `0x0016FAE8` is the sole direct caller of the grounded
`CProfile::SaveGame` entry. Before that handoff the menu selects profile target
zero and, when needed, creates and saves the profile. A valid game-save fixture
must therefore restore a live `GSavePacifyMenu` with the matching profile/card
and permit its process ticks to reach the handoff. A generic save-menu screen,
synthetic direct call, or unrelated card cannot substitute for that boundary.

### Finding (2026-08-31, save-menu activation discriminator)

The game-save phase now invokes the live menu's grounded `ActivateFocused`
action instead of emulating Cross and records the exact
`GSavePacifyMenu::Process` PC (`0x00202F40`) before accepting a save boundary.
On `save-menu.p2s` with the supplied profile card, the deferred activation
completed but observed zero pacify-process calls, zero `CProfile::SaveGame`
entries, and no card delta. This proves that the state has the wrong focused
item or menu level for the normal save path; the prior Cross injection was not
the root cause. Future evidence must include a positive pacify-process count,
so a direct or unrelated save cannot certify the menu-owned operation.

The known `pause-menu.p2s` is also not the missing fixture. Its grounded
Down/Activate/Activate sequence completed all three original menu calls, yet
again observed zero pacify-process calls, zero save entries, and no card delta.
The sequence is rejected rather than encoded as probe policy. Obtaining the
fixture now requires observing the concrete focused-item action at each menu
transition, not choosing another fixed input sequence.

Focused-item action introspection now reports whether the callback-registry
focus is a readable `GMenuItem` action without changing menu semantics. On the
same save-menu state, the callback menu had no focused item, while the grounded
dispatch-bound pointer path focused item `0x015AFD10` and invoked its original
pointer action with exact stack restoration. That action still recorded zero
pacify calls, save entries, and card delta. Pointer focus and menu focus are
therefore distinct owners; neither may be treated as a normal save fixture
without the pacify boundary.

`CCRC32::GetCRC` uses a reflected CRC-32 table with initial value
`0xFFFFFFFF` and no final XOR (equivalently `zlib.crc32(name) ^ 0xFFFFFFFF`).
This resolves the pointer evidence: its inherited focus was `LoadMenu`
(`0xCA788CFB`), while the measured button was `CancelKillMe`
(`0x95DF2577`). The available save-menu state has a cancellation path, not a
save-slot action, which explains the zero pacify-process count without
speculating about profile or card failure.

### Finding (2026-08-31, guest shutdown seam)

The generic menu action `QuitGame` reaches `CShell::Quit` at `0x0016F8D0`
through `GMenu::ItemActivated`; it sets shell state `+0x808` to the quit bit
`4`. `CShell::MainLoop` reads that bit immediately after `ProcessOSUpdates` and
returns at `0x0016F8C8` from its next loop iteration. This gives shutdown a
guest-owned request and completion pair: validate `CShell::Quit` against the
live shell singleton at `0x003672F0`, then observe that main-loop return. The
control channel's VM shutdown route is not evidence for this game path.

### Finding (2026-08-31, normal game-load owner)

`GLoadPacifyMenu::Process` at `0x00202C20` waits for two process ticks, clears
game statistics, selects profile target zero, and calls `CShell::LoadGame` with
the selected slot. That shell function schedules the load bit; the next
`CShell::MainLoop` pass calls `CProfile::LoadGame` at `0x00130000` from
`0x0016F7CC`. A normal game-load fixture must therefore restore a live load
pacify menu and its matching profile/card until this deferred shell handoff;
a direct profile call or an arbitrary load-confirmation dialog is not the
game-owned path.

The retained trace set is mechanically summarized by
`tools/analyze_bios_traces.py`, which reuses the runner's strict v5 validator
and groups only events actually present in each capture. Schema v5 separately
counts grounded results, returned oracle calls, returned void calls, unobserved
results, and non-returning transfers. The earlier seven
v1 captures remain phase-boundary and service-identity evidence, but their
sampled `v0` values were pre-dispatch registers and are no longer accepted as
results by the analyzer.

### Finding (2026-08-29, mission-state repeatability control)

Two fresh `mission1.p2s` statefile-to-running captures were both accepted as
bounded traces, but the first contained 237 events (2 EE syscalls, 84
exceptions, and 151 timers) and the immediate repeat contained only one timer
event. This is negative repeatability evidence: the state-restore callback and
capture route still do not define a guest-owned completion/quiescence boundary.
The traces must not be combined into a claimed mission-service inventory.

### Finding (2026-08-29, clean stream import census)

The first recompiler change routed every import-looking `addiu` through the
interpreter dispatcher and produced 54 million dropped trace events during a
clean stream probe. Static inspection and live snapshots separated the causes:
unhandled import-looking probes, then hot EE exception/syscall and timer
repetition. The final narrow implementation keeps the existing recompiler HLE
and debug path, admits only recognized HLE/debug imports, and coalesces repeated
identities in the observation sink. A Clang-built clean-boot native stream
probe then completed with 11 recognized import identities, including
`ioman.read` and `cdvdman` read/seek/getError/searchFile, 1,290 retained event
identities, and zero overflow. The native stream proof also recorded two
completed `MENU01.ZIV` sector reads.

### Finding (2026-08-29, static EE syscall candidates)

`tools/analyze_ee_syscalls.py` now scans executable PT_LOAD code from the
user-supplied ELF without tracking the asset. On `SLUS_201.47` it found one
executable segment, 158 embedded BIOS wrapper definitions, 458 direct wrapper
callsites, and 8 direct syscall instructions, covering 63 statically decoded
syscall numbers. The scanner keeps static candidates separate from runtime
observations and cannot see indirect or data-driven dispatch; it therefore
narrows the next runtime inventory but does not establish service execution or
results.

### Finding (2026-08-29, grounded mission boundary seam)

The BIOS phase runner now waits for the existing native `MENU01.ZIV`
readiness boundary, arms a one-shot observer through the shared EE execution
instrumentation, and pairs `CShell::ShellLoadLevel` entry `0x0016F910` with
the first post-load point `0x0016FA4C`. It records the two guest clocks,
frame, ordinal, and host time, rejects wrong ordering or duplicate points, and
returns a bounded refusal when the return is absent. A 180-second Clang-built
clean-boot run reached native `MENU01` readiness and the M1 trigger, but the
mission capture returned HTTP 504 because the grounded return was not observed
within its five-second deadline. The seam is therefore exercised but no
mission boundary or service-level runtime claim is accepted.

### Finding (2026-08-30, mission archive makes bounded forward progress)

The mission probe's `GAvPWorld != 0` check remains an early progress marker,
not completion of `CShell::ShellLoadLevel`. Static call-graph and disassembly
evidence corrected the earlier timeout-PC interpretation: `0x002CE88C` is the
bounded normalization loop in `litodp`, reached through `__floatdisf` from the
title's TBF loading callbacks. It is not evidence of a hang in `__pack_d`.

The 360-second runner attempt previously described as never reaching
`Running` did reach the verified boundary, then ended normally when the inner
mission capture returned its bounded failure. Its control profile had
`EnableEE=false`, so the dynarec-only boundary observer could not produce valid
evidence. The isolated test profile now explicitly sets
`EmuCore/CPU/Recompiler.EnableEE=true`, and the runner reports the accepted
`Running` status before starting long probes.

The mission observer now distinguishes exact `CTbdFile::Error`, `ReadChunk`
entry, callback, and epilogue PCs from the two exact ShellLoadLevel boundary
PCs. Its production-order regression rejects progress PCs as mission returns.
A valid Clang-built surfaceless/native run reached `Running`, the exact mission
entry, and the early world endpoint, then returned HTTP 504 after 120 seconds
with no ShellLoadLevel return and no loader error. During that interval it
observed 124 ReadChunk starts, all 124 completions, and 124 callbacks to
`GMissionGoalsMenu::LoadHackCallback` at `0x00204AC0`, with zero invalid stack
reads. A repeated payload-accounting run measured 4,029,554 bytes across the
same 124 completed chunks; the largest was 868,004 bytes, the last was 228
bytes, and none crossed the 1 MiB slice boundary. The timeout sampled the
same floating-point runtime beneath the callback. The timing refinement
corrected that count-only interpretation: a valid run completed all 124 chunks
in 1.164733261 s/67 frames from first entry to last return. Chunk bodies
consumed 0.435780112 s, callbacks 0.022820176 s,
payload/read/decompression 0.388417553 s, and the 123 inter-chunk gaps
0.728953149 s. The remaining approximately 119 seconds are after the final
chunk, with no loader error and no mission return. The timeout debug PC is only
an instantaneous sample and cannot overrule the paired timing evidence. This
proves a completed small-record archive burst rather than a stuck chunk, one
giant transfer, or a retry loop; it still does not establish a completed
mission service slice.

The next exact-PC partition further grounds the missing return. Twenty-two
`LoadCore` rounds reached EOF, escaped `_WatchCount`, and completed offsets,
externs, publics, and handles; only 21 completed `InitTypes` and returned.
Nested-round tracking ended at depth zero, next expected
`init_types_complete`, with zero sequence errors. Static disassembly places
the active work in the outer `InitTypes` indirect initializer call at
`0x0017467C`; its nested `LoadCore` has already returned.

### Finding (2026-08-30, completed mission boundary)

The stack-paired initializer observer identified the active target as
`CPresetFillData`; a second stack-paired factory observer identified
`GExitMissionGoalsButton::Create`. Static RE established that the constructor
enters the synchronous `GMissionGoalsMenu::LoadHackCallback` loop and polls
`GInputDevice` before the ordinary callback registry owns the menu. The prior
timeout was therefore the title waiting in a load modal, not a stalled BIOS,
IOP, archive, or type initializer.

`NativeEeExecutionHooks` now composes the mission timing and BIOS observers at
the shared interpreter/recompiler seams. `NativeHostYield` pumps pending host
CPU transactions only at the exact modal loop PC. `NativeMenuInput` waits for
the exact Exit object, focuses it through its grounded virtual, and invokes
`GMenu::Input(Activate)` synchronously; deferred dispatch is unsafe at this
reentrant PC because the original guest execution can falsely look like the
queued call's return.

A valid clean mission capture reached `ShellLoadLevel` continuation
`0x0016FA4C` with no loader error, 134/134 observed chunks, all 24 post-read
rounds, 2,638/2,638 initializer calls/returns, 942/942 factory calls/returns,
and zero mission/post-read/initializer/factory sequence errors. The exact Exit
object was focused and activated in 3,609 EE cycles with stack restoration, and
the mission menu singleton cleared. The separate single-active-frame load-
timing observer reported 10 nesting errors, so its timing totals are not used
for this path.

### Finding (2026-08-30, result-boundary correction and mission census)

Schema v1 sampled EE `v0` before BIOS dispatch and sampled IOP `v0` before an
oracle fallback completed. It then coalesced services without preserving valid
result variation. The impossible values in the first completed mission report
falsified C031 and every downstream v1 return-value claim.

Schema v2 records explicit `bios`/`direct` and `oracle`/`hle` outcomes, omits a
result for BIOS/oracle ownership, snapshots IOP arguments before HLE dispatch,
and rejects legacy or malformed artifacts. Three clean v2 captures completed the
grounded mission boundary with zero overflow. They repeated the same 11 EE
syscall and 4 IOP import service identities and exactly matched all import
summaries. The only service-count delta was BIOS `sceSifSetDma`, at 1,126
versus 1,125 calls. Every syscall result remains unobserved at this entry seam;
`sceCdGetError` likewise remained oracle-owned. Handled `ioman.read`,
`ioman.lseek`, and `sysmem.Kprintf` calls carried grounded result sets.

The combined Clang analyzer also exposed an existing ioman/iomanX directory-
read defect: both HLE paths copied complete directory-entry structs to guest
memory even though their stack buffers were uninitialized before the host
owner filled named fields. Both buffers are now value-initialized, preventing
indeterminate padding or untouched fields from entering guest-visible state.

### Finding (2026-08-30, grounded EE BIOS return and result disposition)

The generalized v2 direct-result contract was false: `GetOsdConfigParam2` and
the recompiler's constant `FlushCache` path return directly without assigning
`v0`. The first BIOS-return experiment was also false: sampling every COP0
`ERET` paired 13,566 ordinary returns but treated 1,706
`ResumeIntrDispatch` context restores as missing returns, producing 1,705
superseded frames and one pending frame. Current ps2sdk syscall identities and
declarations establish that control return, result existence, and result width
are independent ABI facts.

Schema v5 observes the instruction immediately after a syscall through the
shared EE execution hook and pairs it to a pending BIOS entry by stack pointer
and exact resume PC. `NativeBiosEventStore` owns bounded admission,
coalescing, serialization, and pairing separately from trace lifecycle. Its
disposition table classifies supported 32-bit results, void returns,
declared unsigned 64-bit results, unobserved unknown results, and non-returning
calls. The 64-bit result is the full EE `v0`, serialized as `result_u64` rather
than a signed/truncated `result`; `GsGetIMR` and `GsPutIMR` are the grounded
ps2sdk declarations. Validator and inventory tests reject wrong resume PCs,
ambiguous scalar encodings, malformed result fields, legacy schemas, and
overflow, and force returned-void, returned-64-bit, and unobserved-result paths.

Two Clang-built clean mission captures completed the grounded mission boundary.
They paired 13,566/13,566 and 13,565/13,565 return-capable BIOS calls with zero
pending calls, sequence errors, pairing overflow, trace overflow, or mission
sequence errors. Both repeat the same 11 syscall identity/disposition classes.
`ResumeIntrDispatch` is non-returning; `FlushCache` and
`sceSifSetDChain` return control without a result; thread/semaphore calls and
`sceSifSetDma` expose their program-visible signed 32-bit result. Fixed
thread/semaphore result sets repeat. Exact hot-path totals do not:
`sceSifSetDma` differed by one call and direct `FlushCache` by two. C035/I021
therefore claim stable service semantics, not byte-identical traces.

### Investigation (2026-08-30, narrow IOP oracle return boundary)

An unhandled IRX import transfers through its real import-stub target and
eventually resumes at the caller's saved IOP `ra`. Three generalized observer
designs were rejected before evidence capture: locking and scanning pending
frames on every indirect branch, adding an atomic function gate to every
indirect branch, and emitting a pending-return comparison into every recompiled
`JR` block. Each changed a hot shared path unrelated to the one return being
measured.

The current schema-v4 design instead records the import's `sp` and `ra`, keeps
a fixed 256-frame pending set, and admits the return PC through the dedicated
fixed 256-site atomic `NativeIopReturnSites` registry. It invalidates only a
newly registered caller return block and emits the observer only when that exact
block is compiled. The interpreter first checks one pending-call
atomic and consults the exact registry only during an active oracle call, after
completing the branch delay slot. Focused validator, inventory, and
native tests cover wrong boundaries, nested same-boundary calls, duplicate site
registration, counter reconciliation, and returned-result grouping.

The first exact-site implementation still performed a 256-slot registry scan
for every IOP block compilation and every interpreted branch, including before
any site existed. `NativeIopReturnSites` now publishes a contiguous admitted
count: an empty recompiler lookup is one atomic load, later lookups inspect only
admitted sites, and rare registration is serialized. The interpreter's pending
gate prevents any registry lookup outside the active oracle-call interval.

Four fixed-deadline mission attempts made while the host load average exceeded
20 did not reach the existing `MENU01.ZIV` readiness boundary. The first
exact-site design also missed that boundary while unrelated processes occupied
most CPU capacity, and the later audit found its unconditional 256-site scans.
After that scan was removed, a fifth unchanged run reached verified `Running`
but ended at 63,635,456 bytes of `INTRO.PSS` when unrelated compiler work rose
again; a sixth reached 55,574,528 bytes after the same workload surged during
the run. Neither produced a trace artifact. None of these runs is accepted as
semantic or performance evidence.

Two subsequent unchanged-deadline captures in a host window with sustained
idle capacity completed the exact mission boundary. Both paired 527/527 IOP
oracle entries/returns with zero pending calls or overflow. Every paired call
was `cdvdman.sceCdGetError`, returned 0, and used the same stack
`0x001FA510` and caller PC `0x0003CB2C`. Both traces paired 13,565/13,565 EE
BIOS entries/returns with zero pending calls, sequence errors, or overflow. The
two captures repeat the same event-kind, import-identity, and syscall-identity
sets; their 1,358 versus 1,353 retained event identities again show that
hot-path totals are not a repeatability contract.

## Remaining work

Next obtain a guest-owned normal `GSavePacifyMenu::Process` fixture that reaches
the grounded `CProfile::SaveGame` observer, then cover game-load and shutdown.
Add a separate grounded
observation seam for remaining interrupt
delivery, kernel primitives outside the mission slice, executable loading, IOP
module loads and services outside the recognized import surface, and a live
title exercise of the declared 64-bit GS result path, then capture service
negative paths before designing the HLE
implementation.

## Resolution

Not resolved. The current census is the first partial S025 slice; it does not
establish a BIOS-free path or any S026–S028 behavior.
