# AVP:E BIOS/IOP observation contract

The required BIOS/HLE surface is not inventoried yet. This document records
the first observation slices only; it is not an HLE implementation or a claim
that the observed services are the complete firmware contract.

## Structured census

`AVPE::NativeBiosTrace` is a bounded, observation-only event sink. The
surfaceless control-test mode enables it and exposes its snapshot at
`GET /bios/trace`. It records, in one sequence-ordered stream:

- every recognized HLE/debug IOP import identity with library, ordinal,
  resolved name, first four input arguments, handler availability, actual
  `hle` or `oracle` outcome, result validity, and an occurrence count. A
  handled HLE outcome carries its immediate signed `v0`; an oracle outcome
  records the entry stack/return boundary and emits a separate paired return
  event with the eventual signed `v0`;
- every EE `SYSCALL` identity through the shared interpreter implementation,
  with the normalized syscall number, BIOS name, first four argument registers,
  actual `direct` or `bios` outcome, return/result expectations, result validity,
  and an occurrence count. Return-capable BIOS calls pair by guest stack pointer
  and exact post-syscall PC, and emit a separate return event. Declared 32-bit
  results carry the program-visible signed `v0`; declared `u64` results carry
  the full unsigned `v0` as `result_u64`; void returns omit a result; unknown
  result types remain explicitly unobserved;
- the first EE/IOP exception-entry observation for each domain, cause code,
  pre-entry PC, and branch-delay shape, with an occurrence count;
- the first EE/IOP counter observation for each domain, counter, overflow, and
  delivery shape, with count, target, cycle, and an occurrence count;
- `RegisterLibraryEntries` and `ReleaseLibraryEntries` module name/version;
- `RegisterIntrHandler` interrupt number, symbolic name, and handler address;
- `sceSifRegisterRpc` RPC ID.

The sink retains at most 4096 events across all event kinds and reports
overflow explicitly. Repeated recognized imports are coalesced by service
identity, outcome, and valid result and carry a `calls` count so hot polling
cannot consume the census with duplicate events. The retained
`first_arguments` belong to the first call in that coalesced group. It does not
change dispatch, return values, scheduling, or fallback behavior. Unknown
imports remain on PCSX2's existing
unhandled/oracle path and are not counted as recognized service observations.
Both the interpreter and dynarec route the EE `SYSCALL` opcode through the
same implementation, so
the syscall observation is not engine-specific. Schema v1 sampled `v0` before
BIOS dispatch and before IOP oracle fallback completed; those fields were stale
register values. Schema v2 made outcome/result validity explicit but still
mistakenly equated every direct path with a result and had no BIOS return seam.
Schema v3 classifies returning-result, returning-void, unobserved-result, and
non-returning syscalls independently of BIOS/direct ownership. Schema v4 adds
bounded IOP oracle entry/return pairing. `NativeBiosTrace` admits only exact
caller return PCs through the fixed `NativeIopReturnSites` registry; a newly
registered PC invalidates its existing IOP block so the recompiler emits
`NativeIopExecutionHooks` at that block's entry, while the interpreter uses one
pending-call atomic before consulting the exact registry
after a delay slot. Entry and return pair by stack pointer and exact resume PC.
The recompiler adds no work to unrelated blocks, and the interpreter performs
no registry scan outside an active oracle call. The runner rejects v1–v3
artifacts rather than presenting them as current IOP return evidence.

## Static EE syscall candidates

`tools/analyze_ee_syscalls.py` scans only executable `PT_LOAD` segments of a
user-supplied ELF32 little-endian MIPS executable. It recognizes the target's
four-instruction BIOS wrapper shape (`v1` immediate, `syscall`, `jr ra`,
`nop`), records direct `jal` calls to those wrappers, and reports direct
`syscall` instructions separately. It never treats a wrapper definition or a
static callsite as proof that the service ran; indirect calls, data-driven
dispatch, and runtime results remain outside this static scan.

Running it on the ignored user-supplied `scratch/iso/elf/SLUS_201.47` found one
executable segment (`0x00100000`, `0x266d00` bytes), 158 wrapper definitions,
458 direct wrapper callsites, and 8 direct syscall instructions. The union of
the statically decoded call numbers is 63 candidates:
`0x07`, `0x08`, `0x0D`, `0x0E`, `0x10`–`0x17`, `0x1A`–`0x1D`, `0x20`–`0x25`,
`0x29`, `0x2B`, `0x2F`, `0x30`, `0x32`–`0x34`, `0x37`, `0x38`, `0x3C`–`0x3E`,
`0x40`–`0x45`, `0x4A`, `0x4B`, `0x54`, `0x56`, `0x5A`, `0x5B`, `0x64`,
`0x6B`, `0x6F`–`0x71`, `0x73`, `0x74`, `0x76`–`0x7A`, `0x7C`, `0x7F`,
`0x82`, `0x83`, and `0xFC`. This is a candidate inventory only; the bounded
runtime census remains the evidence for execution and handled-HLE results,
while BIOS/oracle results require a separate return seam.

## Boot and savestate captures

`tools/run_control_test.py --probe-bios-trace` starts a fresh BIOS-backed,
surfaceless process, waits for the verified `Running` boundary, then calls
`POST /bios/trace/capture`. With `--statefile`, the same runner resumes a
known BIOS-backed state. The standalone frontend's `Host::OnSaveStateLoaded`
callback resets the observation sink after a successful archive restore and
before the emulation thread enters `Running`; the resulting artifact is
labelled `statefile_to_running` and does not mix restore-time scheduler traffic
with post-restore execution.

The production capture route disables the sink before taking its snapshot while
holding its mutex; any earlier overflow remains explicit in the artifact. The
runner writes artifacts under ignored
`scratch/` storage.

Phase probes capture through `POST /bios/trace/capture-at-guest-boundary`. This
route arms the sink and waits for the next `Counters::VSyncStart` transition on
the emulation CPU thread before atomically disabling and returning the trace.
The five-second deadline refuses a missing guest frame boundary; it is not a
host sleep and does not claim that one frame is a complete guest-owned
quiescence condition. `POST /bios/trace/capture` remains available for
immediate raw diagnostics.

For a later boundary, `POST /bios/trace/start` clears and enables the same sink.
The runner exposes this as `--probe-bios-phase menu` and
`--probe-bios-phase save-load`, both requiring a BIOS-backed `--statefile`.
When `--probe-bios-trace` is combined with the clean-boot native stream probe,
the runner resets the sink at the verified `Running` boundary before waiting
for `MENU01.ZIV`; this isolates the service census from the long bootstrap
timer stream while preserving the ordinary full-boot behavior when no asset
probe is selected.
The menu phase starts a fresh sink, invokes the active game's `down` action,
accepts either its synchronous or deferred completion, and captures the
resulting `statefile_to_menu` slice. The save-load phase saves to an isolated
scratch state, starts a fresh sink, loads the requested state, then invokes the
restored game's exact `down` action and waits for its synchronous or deferred
completion. It snapshots immediately on the emulation CPU thread as
`save_load_to_menu_action`, rather than waiting for an arbitrary next VSync.
Two pause-menu captures retained the same 28 event identities, five fully
paired EE BIOS calls, and zero overflow. This proves the narrow restored-menu
completion boundary and resumed service traffic; it does not claim to observe
archive serialization internals or shutdown after the process exits.

The runner also exposes `--probe-bios-phase mission`, which requires a clean
boot and copied memory card. It waits for native `MENU01.ZIV` readiness, then
arms a one-shot observer on the emulation CPU thread around grounded
`CShell::ShellLoadLevel` entry `0x0016F910` and continuation `0x0016FA4C`.
`NativeEeExecutionHooks` composes the BIOS and mission-timing observers at both
EE engines. Exact loader-error, `ReadChunk`, nested `LoadCore`, indirect
initializer, and object-factory PCs are classified separately; initializer and
factory frames pair by guest stack pointer and remain bounded.

The progress sequence first proved that 124 payload chunks carrying 4,029,554
bytes complete in a 1.164733261 s/67-frame burst with no loader error. It then
identified the active outer initializer as `CPresetFillData` and its active
factory as `GExitMissionGoalsButton::Create`. Static RE showed the constructor
enters `GMissionGoalsMenu::LoadHackCallback`, whose synchronous tight loop polls
`GInputDevice` before normal menu callback registration. `NativeHostYield`
pumps pending host CPU transactions only at that exact loop PC.
`NativeMenuInput` validates the mission menu and exact Exit object, invokes its
exact focus virtual, and activates through `GMenu::Input` synchronously. The
synchronous call is required because a deferred request originating at the
observed loop PC can mistake the original guest block for its own return.

A valid clean native run reached the exact continuation with no loader error,
134/134 observed chunks, all 24 post-read rounds, 2,638/2,638 initializer
calls/returns, and 942/942 factory calls/returns. The mission, post-read,
initializer, and factory sequence counters were zero. The older single-active-
frame timing observer separately reported 10 nesting errors; its timing totals
are not evidence for nested mission reads. The Exit object was focused and
activated in 3,609 EE cycles with stack restoration, and the mission-menu
singleton cleared. The trace establishes a completed mission boundary for
service capture; it does not by itself establish the complete mission service
inventory.

Three repeated captures currently produce the same 28-event slice: 20 module
registrations, 7 IOP exception entries, and 1 IOP timer target event, with zero
overflow. This is repeatability evidence for the boot boundary only; EE
syscall/import activity begins after that boundary and still needs separate
menu, mission, save, and shutdown captures. Three restored states also passed
with zero overflow: the Zono-splash `title-real.p2s` produced 220 events (104
EE syscalls and 116 EE exceptions), `pause-menu.p2s` produced 251 events (2 EE
syscalls, 98 EE exceptions, and 151 EE timers), and `mission1.p2s` produced 71
events (32 EE exceptions and 39 EE timers). The differing mixes demonstrate
that the reset boundary is observing restored guest execution rather than
returning one fixed or stale trace.

A pause-menu `menu_down` phase and the restored-menu save/load phase both
complete with zero overflow. Capture runs on the emulation CPU thread: two menu
runs each produced 7 events (2 EE syscalls and 5 exceptions), while two
save/load repeats retained the same 28 event identities and five fully paired
EE BIOS calls. The restored menu action, not the earlier VSync-only route, is
the guest-owned completion condition for this pause-menu slice.

The Zono-splash title probe presses Start, waits for the callback-registry menu,
then traces the title menu's deferred activation through its exact completion.
Two runs reached that same action with zero overflow, but retained 150 versus
51 event identities (524/524 versus 15/15 paired EE calls; 51/51 versus 0/0
paired IOP oracle calls). It is negative repeatability evidence: title
activation alone is not the required later title-owned service boundary.

Two fresh `mission1.p2s` statefile-to-running captures on 2026-08-29 also
demonstrated that boundary defect: the first contained 237 events (2 EE
syscalls, 84 exceptions, and 151 timers), while the immediate repeat contained
only one timer event. Both captures passed the bounded-trace validator, but
their different lengths make them negative repeatability evidence rather than
a mission-service inventory.

The game-save observer is grounded at `CProfile::SaveGame` entry `0x00130170`
and its final `jr ra` at `0x00130374`; it validates the live `CProfile`
singleton before starting the census and captures the returned signed `v0`
before the jump. Its first fixture discriminator is negative: `save-menu.p2s`
did not enter that owner or change the isolated card after either the
dispatch-bound pointer activation or title Cross input. Generic menu `down`
also returned with no focused object. The observer deliberately retained zero
events rather than attributing pre-selection or resumed traffic to a game save.
This state is not a normal `GSavePacifyMenu::Process` completion; a fixture
that reaches that guest-owned path is still required.

Static RE grounds that path: `GSavePacifyMenu::Process` (`0x00202F40`) waits
for its third process tick, selects profile target zero, conditionally creates
and saves the profile, then calls `CShell::SaveGame` (`0x0016FAE0`). Its call
at `0x0016FAE8` is the only direct caller of `CProfile::SaveGame`. Thus the
future state/card fixture must preserve a live pacify menu, matching profile,
and enough normal process execution to reach that handoff; direct invocation
or a generic save menu would bypass the boundary being inventoried.

The game-save proof additionally requires a positive observation at
`GSavePacifyMenu::Process` (`0x00202F40`) before it accepts the save entry and
return. The corrected native `ActivateFocused` probe completed on
`save-menu.p2s` but recorded zero such calls, zero save entries, and no card
delta, proving that state has the wrong focused item or menu level rather than
an unproven save failure.

The grounded Down/Activate/Activate path from `pause-menu.p2s` also completed
without reaching the pacify process or changing the isolated card. It is not
kept as a probe sequence: the next fixture operation must observe the concrete
focused-item action at each transition rather than guess another input order.

The callback menu focus can be absent even while the dispatch-bound pointer has
focused a valid button. In `save-menu.p2s` that pointer focused `0x015AFD10`
and its original activation restored the stack, but it still did not reach the
save pacify boundary. Pointer and menu focus are distinct evidence and must not
be conflated when constructing the fixture.

The focused-item actions resolve through the title's CRC convention: reflected
CRC-32 with initial `0xFFFFFFFF` and no final XOR. The inherited pointer focus
is `LoadMenu` (`0xCA788CFB`) and the measured button is `CancelKillMe`
(`0x95DF2577`), proving the retained state exposes cancellation rather than a
save slot.

The guest shutdown path has an equivalent static seam. `GMenu::ItemActivated`
handles a `QuitGame` item by calling `CShell::Quit` (`0x0016F8D0`), which sets
the shell quit bit at `+0x808`. `CShell::MainLoop` checks that bit after
`ProcessOSUpdates` and returns at `0x0016F8C8` on the following loop iteration.
A shutdown census must validate the shell singleton at `0x003672F0` and span
that live-menu activation through this main-loop return; the diagnostic VM
shutdown endpoint is unrelated host lifecycle evidence.

`GsGetIMR` does not supply another title phase. Its only static caller is the
SDK store-image helper used by `ps2_screen_capture_GetImage`; that path is
guarded by poll index one in `CPS2Input::PollDevices`, but the input loop starts
at index zero and returns immediately after that one iteration. It is dead
player-two screen-capture support rather than a normal AVP:E renderer service.

The normal game-load path is also deferred through the shell. After two process
ticks, `GLoadPacifyMenu::Process` (`0x00202C20`) selects the profile and calls
`CShell::LoadGame`; this sets the shell load bit. `CShell::MainLoop` consumes
that bit and calls `CProfile::LoadGame` from `0x0016F7CC`. The load census must
therefore use a live load-pacify fixture and observe this shell handoff, rather
than invoke `CProfile::LoadGame` directly or treat a load-confirmation dialog
as completion. `NativeGameLoadBoundary` scopes BIOS/IOP capture from the
profile-validated entry `0x00130000` to its final `jr $ra` at `0x00130168`; the
load-pacify process PC `0x00202C20` is reported as a denominator, not used as
a substitute for the profile call.

Two clean schema-v3 mission captures pair every return-capable BIOS entry at
the exact instruction after its syscall. The runs recorded 13,566/13,566 and
13,565/13,565 entries/returns, with zero pending calls, sequence errors,
pairing overflow, trace overflow, or mission-boundary errors. Both repeat the
same 11 EE syscall identities and the same result-disposition class for each.
`ResumeIntrDispatch` is a non-returning context restore and never enters pairing
state. `FlushCache` and `sceSifSetDChain` return control but are declared void,
so their 18/16 and 1,706 calls respectively carry no invented result. The
thread/semaphore calls and `sceSifSetDma` carry their program-visible signed
32-bit result. Hot totals remain scheduling-sensitive: `sceSifSetDma` differed
by one call and direct `FlushCache` differed by two, so exact event equality is
not claimed.

## Inventory analysis

`tools/analyze_bios_traces.py` consumes one or more captured artifact files and
emits `avpe-bios-inventory-report-v4`. Its summaries preserve the phase and
statefile labels, count retained event identities, group observed EE syscalls
and IOP imports by identity with occurrence counts, and group module,
interrupt, and RPC registrations. Exception domains/codes/PCs and timer
delivery/overflow outcomes are reported separately. For EE syscalls and IOP
imports it separately counts observed results, returned void calls, unobserved
results, and non-returning transfers. It calls the same strict
`bios_trace_is_verified()` policy used by the runner, so a legacy, malformed,
incomplete, or overflowed capture is rejected
rather than summarized.

The earlier seven-capture v1 report remains phase-boundary and event-identity
evidence, but every claimed v1 syscall/import result is withdrawn because the
sink sampled `v0` before the BIOS/oracle owner returned. The three v2 mission
captures remain entry/import identity evidence, but C034 and I020 are
falsified/distrusted for generalized result semantics. Two clean v3 mission
captures supersede their EE return evidence. Both completed the exact mission
boundary, repeated the same 11 syscall identity/disposition classes, and paired
every return-capable BIOS call. The fixed thread/semaphore result sets repeated;
SIF DMA transaction IDs and hot call totals are scheduling-sensitive.
Two clean v4 captures supersede the remaining IOP result gap. Both paired
527/527 `cdvdman.sceCdGetError` oracle entries/returns with result 0 at stack
`0x001FA510` and caller PC `0x0003CB2C`, zero pending calls, and zero overflow.
Their import and syscall identity sets match; retained event totals differ, so
exact hot-path counts remain outside the repeatability contract. Handled
`ioman.read`, `ioman.lseek`, and `sysmem.Kprintf` retain their grounded HLE
results. This is a stable mission service-semantics slice, not an exhaustive
firmware contract or an HLE implementation.

## Required evidence before S025 can be verified

The census still needs this restored-menu completion pattern extended to title
and mission states, plus a fixture that reaches the grounded game-save observer,
explicit game-load, and shutdown boundaries.
The mission slice now has grounded EE BIOS and IOP oracle-return seams, but
kernel primitives outside that slice, executable loading, timers, interrupt
delivery, IOP module loads and services outside the recognized import surface,
and required negative paths still need separate evidence. A
BIOS-free HLE path and paired success/error comparisons are S026–S028 work and
remain blocked.
