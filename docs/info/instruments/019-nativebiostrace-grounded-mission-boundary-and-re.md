---
id: I019
kind: instrument
status: trusted
created: 2026-08-30
---

## Instrument

NativeBiosTrace grounded mission boundary and ReadChunk progress observer

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

## Known failure modes

The EE execution hooks are emitted only by the recompiler, so the control-test
profile must explicitly keep `EmuCore/CPU/Recompiler.EnableEE=true`. Every
permanently instrumented PC must also be classified by its exact observer;
passing a progress PC through a catch-all boundary branch can create a false
mission return. The production-order regression covers that failure.
The instantaneous `/debug` EE PC is not duration evidence: timeout samples in
floating-point helpers under the loading-icon callback coexist with only
0.022820176 s of measured aggregate callback time. Use the paired aggregate
clocks, not a single sampled PC, to classify elapsed time.

## Re-confirmed 2026-08-30

Fourteen focused Clang production tests and a valid surfaceless/null-muted
mission run verified the bounded timing partition. The run preserved its
structured HTTP 504 diagnostic at
`scratch/control-test/bios-mission-progress-gaps.json` while still failing the
probe, recorded exact mission entry with no return or loader error, and
completed 124/124 chunks between host timestamps 443471480200970 and
443472644934231 ns. The requested artifact now survives structured mission
timeouts; an unstructured timeout still produces no fabricated trace.
