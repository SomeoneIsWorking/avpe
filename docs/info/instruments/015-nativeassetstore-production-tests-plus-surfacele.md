---
id: I015
kind: instrument
status: trusted
created: 2026-08-28
---

## Instrument

NativeAssetStore production tests plus surfaceless native TBF probe

## Validated by

The seven-test suite shows Found for a valid member and InvalidStore/Missing for deliberately wrong tokens, manifests, membership, sizes, hashes, mutations, and duplicate/unsafe records; the real control-test runner then showed the valid TBF path reaching native ioman reads with zero original fallthrough while bootstrap remained optical.

## Known failure modes

- It does not observe mutation of an already-open host descriptor or an
  adversarial content mutation that preserves both file size and modification
  time.
- It does not capture the oracle's post-return guest value or buffer effect, so
  it cannot prove native/oracle failure equivalence.
