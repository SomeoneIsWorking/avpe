---
id: I004
kind: instrument
status: trusted
created: 2026-08-27
---

## Instrument

Native menu navigation/activation/cancel semantic probes in tools/run_control_test.py

## Validated by

The pause probe observed focus change from Resume object `0x015DFB60` to Save
`0x015E0640`, deferred ownership change `0x012E85A0 -> 0x015AFA70`, and virtual
cancel back to `0x012E85A0`. Both deferred calls reported completed status and
exact nonzero stack restoration. The separate Press START probe observed the
required different ownership result `0x01346590 -> 0x0147D230`. Both processes
reported surfaceless/null-muted status and shut down gracefully.

## Known failure modes

The probes certify directions plus activation/cancel in the saved pause and
Press START states. They do not certify mouse hit-testing, every menu subtype,
or delivery from a real product-window key event.
