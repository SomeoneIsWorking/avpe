---
id: C031
kind: claim
status: holds
created: 2026-08-28
tags: bios,hle,iop,inventory
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeBiosTrace.cpp#ObserveMissionLoadProgress
expires_on: a BIOS-backed clean run or production test shows dispatch, return, ordering, or overflow behavior differs from the documented NativeBiosTrace contract, or the trace changes the existing IOP fallback result
reconfirmed: 2026-08-30
verified_at: 2026-08-30 03:25:46
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
`IopBios.cpp` records recognized import results after the existing debug/HLE
dispatch and records registrations at their existing narrow owners. Repeated
recognized import identities are coalesced with a call count; unhandled
import-looking probes remain on the existing oracle path and are excluded.
Repeated EE syscall, exception, and timer identities are coalesced with
occurrence counts for the same bounded-census reason.
`GET /bios/trace`
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

## Re-confirmed 2026-08-28

After making successful `Host::OnSaveStateLoaded()` the post-restore trace
boundary, the Clang build passed and the focused Python policy suite passed 39
tests. BIOS-backed surfaceless/null-muted resumes from `title-real.p2s`,
`pause-menu.p2s`, and `mission1.p2s` captured 220, 251, and 71 ordered events
with zero overflow. Their differing event mixes confirm that the boundary
captures restored execution rather than a fixed clean-boot trace.

## Re-confirmed 2026-08-28

Full verifier passed 117 Python tests, 19 production C++ tests, scoped/full clang-format, and all 45 clang-tidy units. Final Release-built BIOS-backed surfaceless/null-muted title-real.p2s resume captured 220 ordered events with zero overflow; title-real, pause-menu, and mission1 resumes captured 220, 251, and 71 events with differing mixes and zero overflow after Host::OnSaveStateLoaded reset.

## Re-confirmed 2026-08-28

After adding the explicit BIOS phase-start route, the full verifier passed 119
Python tests, 19 production C++ tests, scoped/full clang-format, and all 45
clang-tidy units. A pause-menu `menu_down` phase captured 63 ordered events
and a save-then-load phase captured 62 ordered events; both had zero overflow.
The menu action completed synchronously, while the save/load artifact records
post-load execution and does not claim to observe game-profile serialization.

## Re-confirmed 2026-08-28

Full non-windowed verifier passed 119 Python tests, 19 production C++ tests, scoped/full clang-format, and all 45 clang-tidy units. Release-built BIOS-backed surfaceless/null-muted pause-menu.p2s menu_down capture produced 63 ordered events with zero overflow; save-then-load phase produced 62 ordered events with zero overflow. The mission phase was not accepted because its grounded world endpoint did not occur.

## Re-confirmed 2026-08-28

The committed phase-boundary implementation was verified by the full non-windowed gate: 119 Python tests, 19 production C++ tests, scoped/full clang-format, and all 45 clang-tidy units. Release-built BIOS-backed surfaceless/null-muted pause-menu.p2s menu_down capture produced 63 ordered events with zero overflow; save-then-load phase produced 62 ordered events with zero overflow. The mission attempt was rejected because its grounded world endpoint did not occur.

## Re-confirmed 2026-08-28

After ebd61cd moved POST /bios/trace/capture onto the emulation CPU thread, the full non-windowed verifier passed 120 Python tests, 22 production C++ tests, clang-format, and 46 clang-tidy translation units. Two identical pause-menu menu-down phase runs each captured 7 ordered events (2 EE syscalls and 5 exceptions) with zero overflow. Two save-load runs captured 34 and 31 ordered timer events with zero overflow, exposing that archive restoration still lacks a guest-owned completion boundary; no arbitrary delay was added.

## Re-confirmed 2026-08-29

The new `bios_inventory` seam reuses `bios_trace_is_verified()` and rejects
invalid or overflowed artifacts before grouping their observed events. Its
tests cover service identity aggregation, distinct return values, runtime
exception/timer categories, and multi-capture totals. Running
`tools/analyze_bios_traces.py` over two repeated clean boots, one title-real
resume, two menu captures, and two save-load captures produced a 7-capture,
335-event report. Those runtime artifacts contain EE syscalls, module
registrations, EE/IOP exceptions, and EE timers; they contain no IOP import,
interrupt-registration, or RPC events in the selected windows. This improves
inventory accounting but does not close the guest-owned save/load boundary or
complete the firmware census.

## Re-confirmed 2026-08-29

The Clang-built clean-boot native stream proof passed with the recompiler
observation hook, retaining 1,290 event identities with zero overflow and 11
recognized IOP import identities. The trace included `ioman.read` and the
`cdvdman` read/seek/getError/searchFile services; repeated identities carried
occurrence counts. The same run completed two native `MENU01.ZIV` sector reads
with two consumed CDVD completion records. Focused core tests passed 111 tests,
including repeated import, timer, syscall, and exception coalescing.

## Re-confirmed 2026-08-29

After parent a764fa0 and fork 335073a, the full non-windowed verifier passed 131 Python tests, 22 native production tests, scoped/full clang-format, and 46 clang-tidy translation units. The new POST /bios/trace/capture-at-guest-boundary route arms NativeBiosTrace and captures on Counters::VSyncStart on the emulation CPU thread, with a bounded five-second refusal when no boundary arrives. A BIOS-backed surfaceless/null-muted pause-menu run completed through this route with zero overflow; a repeated run also completed with zero overflow but retained a different 21-versus-11 event identity set, so the route removes the HTTP frame-position race without falsely claiming post-restore quiescence.

## Re-confirmed 2026-08-29

Re-verified after parent a764fa0 and fork 335073a: 131 Python tests, 22 native tests, format, and 46-unit Clang-tidy passed. BIOS boundary capture executes at Counters::VSyncStart through NativeBiosTrace::OnGuestFrameBoundary; two pause-menu runs completed with zero overflow, while their differing 21/11 identity sets remain negative repeatability evidence.

## Re-confirmed 2026-08-29

The full Clang verifier passed 154 Python tests, 22 native production tests, clang-format, and 46 clang-tidy translation units. Focused NativeBiosTrace tests passed exact grounded mission entry/return pairing and bounded missing-return timeout. A 180-second Clang-built clean-boot run reached native MENU01 readiness and the grounded M1 trigger but returned HTTP 504 because ShellLoadLevel return 0x0016FA4C was not observed within five seconds; this negative result does not claim mission completion or service-level coverage.

## Re-confirmed 2026-08-29

Post-landing verification passed 155 Python tests, 22 native production tests, clang-format, and 46 clang-tidy translation units with the grounded mission seam at parent 9fe73d4 and nested fork 36890d5. Focused NativeBiosTrace tests cover exact entry/return pairing and bounded missing-return refusal. The clean-boot mission attempt reached native MENU01 readiness and the M1 trigger but returned HTTP 504 because ShellLoadLevel return 0x0016FA4C was not observed within five seconds; this negative runtime result does not claim mission completion or service-level coverage.

## Re-confirmed 2026-08-30

The focused Clang build passed 153 Python tests and 12 NativeBiosTrace tests.
The mission route arms on the emulation CPU thread and waits on the exact guest
return with a bounded 120-second deadline. The earlier 30-second run reached
the grounded entry and early `GAvPWorld` endpoint; its `0x002CE88C` sample is
inside `litodp` under a title loading callback, not evidence of a `__pack_d`
hang. The later attempt did reach verified `Running` and ended through normal
runner shutdown after its bounded inner failure, but its `EnableEE=false`
profile made it invalid evidence for the dynarec observer. No mission
completion or service-level runtime claim is made from those runs.

## Re-confirmed 2026-08-30

2026-08-30: full Clang verifier passed 154 Python tests, 22 native production tests, clang-format, and 46 clang-tidy translation units. The mission boundary route arms on the emulation CPU thread and retains a bounded structured refusal; runtime attempts did not establish a mission return, so no mission service claim is added.

## Re-confirmed 2026-08-30

2026-08-30 post-landing: full Clang verifier passed 154 Python tests, 22 native production tests, clang-format, and 46 clang-tidy translation units. The mission boundary route arms on the emulation CPU thread and retains a bounded structured refusal; runtime attempts did not establish a mission return, so no mission service claim is added.

## Re-confirmed 2026-08-30

Full Clang verifier passed 154 Python tests, 22 native production-path tests, clang-format, and 46 clang-tidy translation units. Fourteen focused NativeBiosTrace tests include production-order rejection of progress PCs as false mission returns plus success, timeout, loader-error, and ReadChunk-progress outcomes. A valid surfaceless/native mission run reached verified Running and exact ShellLoadLevel entry, then reported no return/error with 124 ReadChunk starts, 124 completions, 124 callbacks to 0x00204AC0, and zero invalid stack reads.

## Re-confirmed 2026-08-30

Full Clang verifier again passed 154 Python tests, 22 native production-path tests, clang-format, and 46 clang-tidy translation units after payload accounting. Fourteen focused NativeBiosTrace tests include a 2.5 MiB multi-slice OTHER answer. A valid surfaceless/native mission run reached verified Running and exact entry, then reported no return/error; 124/124 completed chunks carried 4,029,554 bytes, maximum 868,004, final 228, zero multi-slice chunks, and 124 callbacks to 0x00204AC0.
