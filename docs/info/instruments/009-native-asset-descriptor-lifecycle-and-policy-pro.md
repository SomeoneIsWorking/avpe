---
id: I009
kind: instrument
status: trusted
created: 2026-08-27
---

## Instrument

Native asset descriptor lifecycle and policy probe in tools/run_control_test.py

## Validated by

Native-root runs reported nonzero TBF opens/reads/bytes/seeks/close and zero bootstrap claims; a no-root run of the same binary reported zero native claims for every path. Live production-policy cases separately produced native-file, refused-access for write and traversal, refused-missing, and unhandled bootstrap.

## Known failure modes

(none recorded yet)
