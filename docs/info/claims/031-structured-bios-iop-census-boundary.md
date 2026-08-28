---
id: C031
kind: claim
status: holds
created: 2026-08-28
tags: bios,hle,iop,inventory
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeBiosTrace.cpp#SnapshotJson, thirdparty/pcsx2/pcsx2/IopBios.cpp#irxImportExec, thirdparty/pcsx2/pcsx2/R5900OpcodeImpl.cpp#SYSCALL, thirdparty/pcsx2/pcsx2/R5900.cpp#cpuException, thirdparty/pcsx2/pcsx2/R3000A.cpp#psxException, thirdparty/pcsx2/tests/ctest/core/avpe_native_bios_trace_tests.cpp
expires_on: a BIOS-backed clean run or production test shows dispatch, return, ordering, or overflow behavior differs from the documented NativeBiosTrace contract, or the trace changes the existing IOP fallback result
reconfirmed: 2026-08-28
verified_at: 2026-08-28 21:48:15
---

## Claim

AVPE has a bounded observation-only structured census at the shared EE syscall,
EE/IOP exception, and existing BIOS/IOP import and registration seams, with
ordered events and explicit overflow, and the census does not alter the
selected HLE/debug/oracle behavior.

## Evidence

The focused Clang production tests cover disabled capture, sequence ordering,
EE syscall arguments, names, and signed return status, EE/IOP exception fields,
module/interrupt/RPC events, import arguments and return status, and the exact
4096-event bound with overflow. `SYSCALL` records at the common interpreter
owner used by both EE engines after dispatch; the exception owners record
before their existing state transitions;
`IopBios.cpp` records import results after the existing debug/HLE dispatch and
records registrations at their existing narrow owners. `GET /bios/trace`
exposes the snapshot for later clean runtime traces.

## What would falsify it

A runtime or production test demonstrates a changed IOP return/fallback,
missing event ordering, an unbounded event store, or a snapshot that reports
events after capture is disabled.

## Re-confirmed 2026-08-28

Post-change Clang production tests passed: NativeBiosTraceTest covers disabled capture, ordered EE syscall/name/arguments plus IOP events, and the exact 4096-event overflow bound; the full AVPE verifier passed 110 Python tests, build, format, and clang-tidy. The common R5900::Interpreter::OpcodeImpl::SYSCALL owner and NativeBiosTrace SnapshotJson implementation are present at the declared dependencies.

## Re-confirmed 2026-08-28

Focused core_test passed all 22 NativeBiosTrace, NativeAssetStore, and NativeCdvdCompletion tests after the EE and IOP exception-entry additions; the full uv run --frozen python tools/verify.py gate also passed 110 Python tests, production C++ tests, scoped clang-format, and all 43 clang-tidy translation units. Exception hooks record before existing state transitions and preserve existing dispatch/fallback behavior.

## Re-confirmed 2026-08-28

After landing submodule 1a0af27, focused core_test passed all 22 NativeBiosTrace, NativeAssetStore, and NativeCdvdCompletion tests; the full uv run --frozen python tools/verify.py gate passed 110 Python tests, production C++ tests, scoped clang-format, and all 43 clang-tidy translation units. Exception hooks record before existing state transitions and preserve existing dispatch/fallback behavior.

## Re-confirmed 2026-08-28

After landing submodule 7d0796f, focused core_test passed all 22 NativeBiosTrace, NativeAssetStore, and NativeCdvdCompletion tests, including a signed negative EE syscall result. The full uv run --frozen python tools/verify.py gate passed 110 Python tests, production C++ tests, scoped clang-format, and all 43 clang-tidy translation units. The shared SYSCALL owner snapshots arguments before dispatch and records v0 after dispatch, preserving mutated input registers and existing early-return behavior.
