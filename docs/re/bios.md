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
- `RegisterLibraryEntries` and `ReleaseLibraryEntries` module name/version;
- `RegisterIntrHandler` interrupt number, symbolic name, and handler address;
- `sceSifRegisterRpc` RPC ID.

The sink retains at most 4096 events and reports overflow explicitly. It does
not change dispatch, return values, scheduling, or fallback behavior. Unknown
imports remain on PCSX2's existing unhandled/oracle path and are recorded with
`hle: false`.

## Required evidence before S025 can be verified

The census still needs clean repeated BIOS-backed traces from boot through a
stable menu, then separate menu, mission, save/load, and shutdown traces. The
later inventory must add EE syscalls, kernel primitives, executable loading,
timers, and interrupt delivery; this IOP import slice cannot stand in for
those contracts. A BIOS-free HLE path and paired success/error comparisons are
S026–S028 work and remain blocked.
