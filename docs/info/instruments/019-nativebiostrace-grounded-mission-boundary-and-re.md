---
id: I019
kind: instrument
status: trusted
created: 2026-08-30
---

## Instrument

NativeBiosTrace grounded mission boundary and ReadChunk progress observer

## Validated by

Clang NativeBiosTrace production tests reject progress PCs as mission returns and exercise success, timeout, loader-error, and chunk-progress results; a 2026-08-30 surfaceless/native mission run reached verified Running then returned HTTP 504 with exact entry, no ShellLoadLevel return/error, 124 ReadChunk starts, 124 completions, 124 callbacks to 0x00204AC0, and zero invalid stack reads.

## Known failure modes

The EE execution hooks are emitted only by the recompiler, so the control-test
profile must explicitly keep `EmuCore/CPU/Recompiler.EnableEE=true`. Every
permanently instrumented PC must also be classified by its exact observer;
passing a progress PC through a catch-all boundary branch can create a false
mission return. The production-order regression covers that failure.
