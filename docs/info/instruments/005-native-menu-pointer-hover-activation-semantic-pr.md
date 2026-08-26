---
id: I005
kind: instrument
status: trusted
created: 2026-08-27
---

## Instrument

Native menu pointer hover/activation semantic probe in tools/run_control_test.py

## Validated by

The pause-menu probe observed two required distinct focus answers: normalized (0.7,0.3) focused Resume object 0x015DFB60 and (0.7,0.4) focused Save object 0x015E0640 through AVP:E MenuCheck. An out-of-range coordinate returned 400 without changing deferred-call state. Activating the second focus completed with exact stack restoration and changed active menu 0x012E85A0 to 0x015AFA70. The runner reported surfaceless/null-muted and graceful shutdown.

## Known failure modes

(none recorded yet)
