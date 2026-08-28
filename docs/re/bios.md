# AVP:E BIOS/IOP observation contract

The required BIOS/HLE surface is not inventoried yet. This document records
the first observation slice only; it is not an HLE implementation or a claim
that the observed imports are the complete firmware contract.

## Structured census

`AVPE::NativeBiosTrace` is a bounded, observation-only event sink. The
surfaceless control-test mode enables it and exposes its snapshot at
`GET /bios/trace`. It records, in one sequence-ordered stream:

- every IOP import dispatch with library, ordinal, resolved name, four input
  arguments, return value, and whether an HLE or debug handler was selected;
- every EE `SYSCALL` dispatch through the shared interpreter implementation,
  with the normalized syscall number, BIOS name, and four argument registers;
- EE and IOP exception-entry boundaries with domain, cause code, pre-entry PC,
  and branch-delay state;
- `RegisterLibraryEntries` and `ReleaseLibraryEntries` module name/version;
- `RegisterIntrHandler` interrupt number, symbolic name, and handler address;
- `sceSifRegisterRpc` RPC ID.

The sink retains at most 4096 events across all event kinds and reports
overflow explicitly. It does not change dispatch, return values, scheduling,
or fallback behavior. Unknown imports remain on PCSX2's existing
unhandled/oracle path and are recorded with `hle: false`. Both the interpreter
and dynarec route the EE `SYSCALL` opcode through the same implementation, so
the syscall observation is not engine-specific.

## Required evidence before S025 can be verified

The census still needs clean repeated BIOS-backed traces from boot through a
stable menu, then separate menu, mission, save/load, and shutdown traces. The
EE syscall stream is an observation boundary, not yet a complete kernel
inventory: kernel primitives, executable loading, timers, interrupt delivery,
and the results of each required service still need separate evidence. A
BIOS-free HLE path and paired success/error comparisons are S026–S028 work and
remain blocked.
