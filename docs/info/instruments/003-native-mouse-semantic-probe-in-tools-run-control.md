---
id: I003
kind: instrument
status: trusted
created: 2026-08-27
---

## Instrument

Native mouse semantic probe in tools/run_control_test.py

## Validated by

The probe showed both required differing answers: primary click changed selected object identity and secondary release changed current-command ID from 0 to 0x60039. It also showed the opposite failure answers for duplicate/unmatched edges (409), an unknown button (400), an invalid live pointer (409), and held-state reset after state load (409 release).

## Known failure modes

(none recorded yet)
