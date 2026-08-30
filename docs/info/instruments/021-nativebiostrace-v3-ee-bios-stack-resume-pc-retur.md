---
id: I021
kind: instrument
status: trusted
created: 2026-08-30
---

## Instrument

NativeBiosTrace v3 EE BIOS stack/resume-PC return pairer, ABI disposition table, strict validator, and deterministic inventory analyzer

## Validated by

The v3-a live capture rejected 1,705 superseded ResumeIntrDispatch frames and one pending frame; mismatched-resume and malformed-result tests force rejection; void/unobserved-result tests force both non-result branches; clean mission captures v3-d and v3-e each completed with exact entry/return totals and zero pending, sequence errors, or overflow while preserving stable identity/disposition classes.

## Known failure modes

- Pairing proves that execution reached the instruction after the same guest
  syscall with the same stack pointer. It does not independently explain a
  service's semantics beyond the ABI declaration and program-visible return
  register.
- Only declared scalar results that fit the signed 32-bit trace field are
  captured. Declared 64-bit and unknown/reserved result types are retained as
  unobserved results, never truncated into evidence.
- Hot-path call totals and SIF DMA transaction IDs vary with scheduling. Stable
  identity/result-disposition classes are the repeatability contract; exact
  whole-trace equality is not.
- IOP oracle-fallback results remain unobserved at the import-dispatch seam.
- The 4096-event capacity and coalesced first-argument samples remain explicit;
  overflow invalidates a capture.
- The current clean mission slice begins after native `MENU01` readiness and is
  not the complete boot, save/load, shutdown, interrupt, or negative-path
  firmware surface.
