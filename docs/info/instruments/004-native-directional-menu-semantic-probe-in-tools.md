---
id: I004
kind: instrument
status: trusted
created: 2026-08-27
---

## Instrument

Native directional menu semantic probe in tools/run_control_test.py

## Validated by

The probe observed the required different answer in AVP:E-owned state: focus changed from Resume object 0x015DFB60 to Save object 0x015E0640. It also exercised the opposite policy answer by requiring unsupported synchronous Activate to return HTTP 400, and produced distinct before/down snapshots before graceful shutdown.

## Known failure modes

This probe certifies returning directional focus changes in the saved pause
menu only. It does not certify focused-item activation, cancel, mouse
hit-testing, other menu types, or the product HostWindow event path.
