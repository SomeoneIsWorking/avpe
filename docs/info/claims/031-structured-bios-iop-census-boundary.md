---
id: C031
kind: claim
status: holds
created: 2026-08-28
tags: bios,hle,iop,inventory
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeBiosTrace.cpp#SnapshotJson, thirdparty/pcsx2/pcsx2/IopBios.cpp#irxImportExec, thirdparty/pcsx2/tests/ctest/core/avpe_native_bios_trace_tests.cpp
expires_on: a BIOS-backed clean run or production test shows dispatch, return, ordering, or overflow behavior differs from the documented NativeBiosTrace contract, or the trace changes the existing IOP fallback result
---

## Claim

AVPE has a bounded observation-only structured census at the existing BIOS/IOP
import and registration seams, with ordered events and explicit overflow, and
the census does not alter the selected HLE/debug/oracle behavior.

## Evidence

The focused Clang production tests cover disabled capture, sequence ordering,
module/interrupt/RPC events, import arguments and return status, and the exact
4096-event bound with overflow. `IopBios.cpp` records import results after the
existing debug/HLE dispatch and records registrations at their existing narrow
owners. `GET /bios/trace` exposes the snapshot for later clean runtime traces.

## What would falsify it

A runtime or production test demonstrates a changed IOP return/fallback,
missing event ordering, an unbounded event store, or a snapshot that reports
events after capture is disabled.
