# AVP:E BIOS/IOP observation contract

The required BIOS/HLE surface is not inventoried yet. This document records
the first observation slices only; it is not an HLE implementation or a claim
that the observed services are the complete firmware contract.

## Structured census

`AVPE::NativeBiosTrace` is a bounded, observation-only event sink. The
surfaceless control-test mode enables it and exposes its snapshot at
`GET /bios/trace`. It records, in one sequence-ordered stream:

- every IOP import dispatch with library, ordinal, resolved name, four input
  arguments, return value, and whether an HLE or debug handler was selected;
- every EE `SYSCALL` dispatch through the shared interpreter implementation,
  with the normalized syscall number, BIOS name, four argument registers, and
  signed `v0` return status captured after dispatch;
- EE and IOP exception-entry boundaries with domain, cause code, pre-entry PC,
  and branch-delay state;
- EE and IOP counter target/overflow events with domain, counter index, count,
  target, cycle, and whether the interrupt was delivered;
- `RegisterLibraryEntries` and `ReleaseLibraryEntries` module name/version;
- `RegisterIntrHandler` interrupt number, symbolic name, and handler address;
- `sceSifRegisterRpc` RPC ID.

The sink retains at most 4096 events across all event kinds and reports
overflow explicitly. It does not change dispatch, return values, scheduling,
or fallback behavior. Unknown imports remain on PCSX2's existing
unhandled/oracle path and are recorded with `hle: false`. Both the interpreter
and dynarec route the EE `SYSCALL` opcode through the same implementation, so
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

The production capture route snapshots and disables the sink while holding its
mutex, so high-rate guest timer/syscall traffic cannot overflow the bounded
trace while it is being read. The runner writes artifacts under ignored
`scratch/` storage.

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

## Required evidence before S025 can be verified

The census still needs BIOS-backed traces through a stable menu, plus separate
menu, mission, save, load, and shutdown traces. The
EE syscall stream is an observation boundary, not yet a complete kernel
inventory: kernel primitives, executable loading, timers, interrupt delivery,
and the results of each required service still need separate evidence. A
BIOS-free HLE path and paired success/error comparisons are S026–S028 work and
remain blocked.
