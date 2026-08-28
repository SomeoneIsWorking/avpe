---
id: C031
kind: claim
status: holds
created: 2026-08-28
tags: bios,hle,iop,inventory
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeBiosTrace.cpp#SnapshotJson, thirdparty/pcsx2/pcsx2/AVPE/NativeBiosTrace.cpp#SnapshotAndDisableJson, thirdparty/pcsx2/pcsx2/AVPE/AVPE.cpp#dispatch, thirdparty/pcsx2/pcsx2/IopBios.cpp#irxImportExec, thirdparty/pcsx2/pcsx2/IopCounters.cpp#_rcntFireInterrupt, thirdparty/pcsx2/pcsx2/R5900OpcodeImpl.cpp#SYSCALL, thirdparty/pcsx2/pcsx2/R5900.cpp#cpuException, thirdparty/pcsx2/pcsx2/R3000A.cpp#psxException, src/avpe/native_bios_probe.py#bios_trace_is_verified, tools/run_control_test.py#main, thirdparty/pcsx2/tests/ctest/core/avpe_native_bios_trace_tests.cpp
expires_on: a BIOS-backed clean run or production test shows dispatch, return, ordering, or overflow behavior differs from the documented NativeBiosTrace contract, or the trace changes the existing IOP fallback result
reconfirmed: 2026-08-28
verified_at: 2026-08-28 22:17:22
---

## Claim

AVPE has a bounded observation-only structured census at the shared EE syscall,
EE/IOP exception, and existing BIOS/IOP import and registration seams, with
ordered events and explicit overflow, and the census does not alter the
selected HLE/debug/oracle behavior.

## Evidence

The focused Clang production tests cover disabled capture, sequence ordering,
EE syscall arguments, names, and signed return status, EE/IOP exception fields,
EE/IOP timer target/overflow fields, module/interrupt/RPC events, import
arguments and return status, and the exact 4096-event bound with overflow. `SYSCALL`
records at the common interpreter owner used by both EE engines after dispatch;
the exception owners record before their existing state transitions; the EE and
IOP counter owners record each target/overflow attempt and its delivery
outcome;
`IopBios.cpp` records import results after the existing debug/HLE dispatch and
records registrations at their existing narrow owners. `GET /bios/trace`
exposes the snapshot for later clean runtime traces.

Three repeated BIOS-backed surfaceless clean boots captured the same 28-event
boot-to-`Running` slice with zero overflow through the atomic capture route.
The artifact is explicitly limited to that boundary; it does not establish
later EE syscall/import or game-service phase coverage.

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

## Re-confirmed 2026-08-28

After landing submodule c429234, focused core_test passed all 22 NativeBiosTrace, NativeAssetStore, and NativeCdvdCompletion tests, including EE syscall signed return, exception, and IOP timer delivery fields. The full uv run --frozen python tools/verify.py gate passed 110 Python tests, production C++ tests, scoped clang-format, and all 44 clang-tidy translation units. The shared SYSCALL owner snapshots arguments before dispatch and records v0 after dispatch; the IOP counter owner records target/overflow delivery outcomes without changing timer behavior.

## Re-confirmed 2026-08-28

After landing submodule 7740773, focused core_test passed all 22 NativeBiosTrace, NativeAssetStore, and NativeCdvdCompletion tests, including EE/IOP timer fields with positive and suppressed delivery outcomes. The full uv run --frozen python tools/verify.py gate passed 110 Python tests, production C++ tests, scoped clang-format, and all 45 clang-tidy translation units. EE and IOP counter owners record target/overflow attempts without changing counter transitions or interrupt behavior.

## Re-confirmed 2026-08-28

After adding the atomic POST /bios/trace/capture boundary and the clean-boot runner policy, the focused NativeBiosTraceTest suite passed all 4 tests including capture-disable behavior. Three repeated BIOS-backed surfaceless clean boots each captured the same 28 ordered events (20 module registrations, 7 IOP exceptions, 1 IOP timer), with zero overflow, and shut down cleanly. The full uv run --frozen python tools/verify.py gate passed 115 Python tests, production C++ tests, scoped clang-format, and all 45 clang-tidy translation units.
