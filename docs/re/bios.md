# AVP:E BIOS/IOP observation contract

The required BIOS/HLE surface is not inventoried yet. This document records
the first observation slices only; it is not an HLE implementation or a claim
that the observed services are the complete firmware contract.

## Structured census

`AVPE::NativeBiosTrace` is a bounded, observation-only event sink. The
surfaceless control-test mode enables it and exposes its snapshot at
`GET /bios/trace`. It records, in one sequence-ordered stream:

- every recognized HLE/debug IOP import identity with library, ordinal,
  resolved name, first four input arguments, first return value, handler
  selection, and an occurrence count;
- every EE `SYSCALL` identity through the shared interpreter implementation,
  with the normalized syscall number, BIOS name, first four argument registers,
  first signed `v0` return status, and an occurrence count;
- the first EE/IOP exception-entry observation for each domain, cause code,
  pre-entry PC, and branch-delay shape, with an occurrence count;
- the first EE/IOP counter observation for each domain, counter, overflow, and
  delivery shape, with count, target, cycle, and an occurrence count;
- `RegisterLibraryEntries` and `ReleaseLibraryEntries` module name/version;
- `RegisterIntrHandler` interrupt number, symbolic name, and handler address;
- `sceSifRegisterRpc` RPC ID.

The sink retains at most 4096 events across all event kinds and reports
overflow explicitly. Repeated recognized imports are coalesced by service
identity and carry a `calls` count so hot polling cannot consume the census
with duplicate events. It does not change dispatch, return values, scheduling,
or fallback behavior. Unknown imports remain on PCSX2's existing
unhandled/oracle path and are not counted as recognized service observations.
Both the interpreter and dynarec route the EE `SYSCALL` opcode through the
same implementation, so
the syscall observation is not engine-specific.

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
scratch state, starts a fresh sink, loads the requested state, and captures
the `save_load_to_running` slice after the successful load callback reset. It
proves the control boundary and resumed service traffic; it does not claim to
observe archive serialization internals or shutdown after the process exits.

Three repeated captures currently produce the same 28-event slice: 20 module
registrations, 7 IOP exception entries, and 1 IOP timer target event, with zero
overflow. This is repeatability evidence for the boot boundary only; EE
syscall/import activity begins after that boundary and still needs separate
menu, mission, save, and shutdown captures. Three restored states also passed
with zero overflow: `title-real.p2s` produced 220 events (104 EE syscalls and
116 EE exceptions), `pause-menu.p2s` produced 251 events (2 EE syscalls, 98 EE
exceptions, and 151 EE timers), and `mission1.p2s` produced 71 events (32 EE
exceptions and 39 EE timers). The differing mixes demonstrate that the reset
boundary is observing restored guest execution rather than returning one fixed
or stale trace.

A pause-menu `menu_down` phase and a pause-menu save/load phase both complete
with zero overflow. Capture now runs on the emulation CPU thread: two menu
runs each produced 7 events (2 EE syscalls and 5 exceptions). Save-load runs
produced 34 and 31 timer events, so archive restoration still lacks a
guest-owned completion/quiescence boundary and is not repeatability evidence.

Two further pause-menu captures used the CPU-owned frame-boundary route. They
remained bounded with zero overflow but retained 21 and 11 event identities,
respectively; their exception and syscall identity sets differed. The frame
transition removes the control request's frame-position race, but it does not
establish a stable post-restore guest completion condition. This is negative
repeatability evidence, not menu-service coverage.

Two fresh `mission1.p2s` statefile-to-running captures on 2026-08-29 also
demonstrated that boundary defect: the first contained 237 events (2 EE
syscalls, 84 exceptions, and 151 timers), while the immediate repeat contained
only one timer event. Both captures passed the bounded-trace validator, but
their different lengths make them negative repeatability evidence rather than
a mission-service inventory.

## Inventory analysis

`tools/analyze_bios_traces.py` consumes one or more captured artifact files and
emits `avpe-bios-inventory-report-v1`. Its summaries preserve the phase and
statefile labels, count retained event identities, group observed EE syscalls
and IOP imports by identity with occurrence counts, and group module,
interrupt, and RPC registrations. Exception domains/codes/PCs and timer
delivery/overflow outcomes are reported separately. It calls the same strict
`bios_trace_is_verified()` policy used by the runner, so an incomplete or
overflowed capture is rejected rather than summarized.

For the retained evidence set containing two repeated clean boots, one
title-real resume, two menu captures, and two save-load captures, the analyzer
reported 7 captures and 335 total events. Runtime observations covered EE
syscalls, module registration, EE/IOP exceptions, and EE timers. It observed no
runtime IOP import, interrupt-registration, or SIF-RPC events in those phase
windows; their presence in production tests is not a substitute for a title
runtime capture. The observed EE syscall identities in that set were
`RotateThreadReadyQueue` (#43, results 0 and 1), `sceSifSetDma_isceSifSetDma`
(#119, result 0), `sceSifSetDChain_isceSifSetDChain` (#120, result 0),
`iSignalSema` (#67, result 0), `RFU005` (#5, result 0), `DeleteSema` (#65,
result 11), `CreateSema` (#64, result 0), and `WaitSema` (#68, with distinct
wait arguments and nonzero observed return values). These are service-level
observations from the retained windows, not an exhaustive syscall contract.
This is an inventory aid, not a completion boundary and not an HLE
implementation.

## Required evidence before S025 can be verified

The census still needs a guest-owned completion boundary for save/load and
then repeated BIOS-backed traces through stable title/menu
and mission paths, plus explicit service-level save, load, and shutdown
boundaries. The
EE syscall stream is an observation boundary, not yet a complete kernel
inventory: kernel primitives, executable loading, timers, interrupt delivery,
and the results of each required service still need separate evidence. A
BIOS-free HLE path and paired success/error comparisons are S026–S028 work and
remain blocked.
