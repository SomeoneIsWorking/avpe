---
id: I019
kind: instrument
status: trusted
created: 2026-08-30
---

## Instrument

NativeBiosTrace grounded mission boundary, loader progress, initializer, and
object-factory observer

## Validated by

Clang NativeBiosTrace production tests reject progress PCs as mission returns
and exercise success, timeout, loader-error, and chunk-progress results. A
2026-08-30 surfaceless/native mission run reached verified Running then
returned HTTP 504 with exact entry, no ShellLoadLevel return/error, 124
ReadChunk starts, 124 completions, 124 callbacks to `0x00204AC0`, and zero
invalid stack reads. A repeat measured 4,029,554 payload bytes across the same
124 chunks, with an 868,004-byte maximum, a 228-byte final chunk, and zero
multi-slice chunks. The observer now also aggregates whole-chunk, callback,
payload/decompression, and inter-chunk clocks and retains the first chunk entry
and last chunk return. A valid run completed all 124 chunks in a
1.164733261-second burst spanning 67 frames: 0.435780112 s inside chunks and
0.728953149 s across the 123
inter-chunk gaps, with zero timing sequence errors. A two-chunk production test
demonstrates the nonzero inter-chunk answer.

The same bounded observer now pairs indirect `InitTypes` and object-factory
call/return frames by guest stack pointer and reports the active frame without
retaining an unbounded call stream. A valid clean native run demonstrated the
completed answer after earlier bounded timeouts: it identified
`CPresetFillData` and `GExitMissionGoalsButton::Create`, completed all 24
post-read rounds, paired 2,638/2,638 initializer calls/returns and 942/942
factory calls/returns, and reached the exact `ShellLoadLevel` continuation with
zero sequence errors.

## Known failure modes

`NativeEeExecutionHooks` must remain the one composition point called by both
EE engines; bypassing it can silently omit one observer. Validated mission runs
still pin `EmuCore/CPU/Recompiler.EnableEE=true` so their execution profile is
stable. Every permanently instrumented PC must also be classified by its exact observer;
passing a progress PC through a catch-all boundary branch can create a false
mission return. The production-order regression covers that failure.
The instantaneous `/debug` EE PC is not duration evidence: timeout samples in
floating-point helpers under the loading-icon callback coexist with only
0.022820176 s of measured aggregate callback time. Use the paired aggregate
clocks, not a single sampled PC, to classify elapsed time.
The mission-goals modal is synchronous and the control request originates at
its observed loop PC. Queuing its activation as a deferred guest call can
falsely complete on the original guest block; the validated probe must report
the dedicated synchronous execution form and exact Exit target.

## Re-confirmed 2026-08-30

Fourteen focused Clang production tests and a valid surfaceless/null-muted
mission run verified the bounded timing partition. The run preserved its
structured HTTP 504 diagnostic at
`scratch/control-test/bios-mission-progress-gaps.json` while still failing the
probe, recorded exact mission entry with no return or loader error, and
completed 124/124 chunks between host timestamps 443471480200970 and
443472644934231 ns. The requested artifact now survives structured mission
timeouts; an unstructured timeout still produces no fabricated trace.

## Re-confirmed 2026-08-30

Sixteen focused Clang tests cover repeated and nested `LoadCore` phase
sequences plus a skipped-stage OTHER answer. A valid mission capture recorded
22 EOF, watch-release, offsets, externs, publics, and handles points, but only
21 `InitTypes` completions and `LoadCore` returns. The bounded nesting tracker
ended at depth zero, next expected `init_types_complete`, with zero sequence
errors. This grounds the active outer phase inside `InitTypes`; its nested
`LoadCore` had already completed.

## Re-confirmed 2026-08-30

The instrument demonstrated both bounded timeout and completed-return answers.
In the completed clean run, all stack-paired initializer/factory depths returned
to zero, every post-read phase completed, and exact mission entry/continuation
ordering passed. The mission probe separately proved that the synchronous Exit
action targeted the grounded object, restored the stack, cleared the modal
singleton, and enabled the exact return.

## Re-confirmed 2026-08-30

The final combined gate passed 159 Python/structure tests, 22 standard native
production tests, clang-format, and all 49 clang-tidy units. Focused production
coverage passed 19 NativeBiosTrace tests plus the NativeHostYield and
NativeMenuInput source-selection tests. The verifier's explicit inventory now
contains the EE compositor, host-yield owner, and extracted menu route.
