---
id: I001
kind: instrument
status: trusted
created: 2026-08-26
---

## Instrument

`tools/run_control_test.py` runtime isolation and target-boot verifier.

## Validated by

The same acceptance function was fed cases that must differ. It accepted the
complete target/control-test/surfaceless/null-muted/current-nonce fixture and
rejected fixtures with a native surface, a real audio backend, and another
process's nonce. Integration then produced the accepted runtime handshake and
independent log lines for surfaceless acquisition and Null audio.

## Known failure modes

The runner proves the invisible developer control path, not the user-facing
AVPE host window. It cannot certify product resize, focus, fullscreen, RmlUi,
or desktop presentation behavior.
