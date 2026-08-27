---
id: I011
kind: instrument
status: trusted
created: 2026-08-27
---

## Instrument

Native stream-sector probe in tools/run_control_test.py

## Validated by

The real validated-store run accepted one MENU01.ZIV native search, seek, and two sector reads totaling 49,152 bytes. Focused negative fixtures with no native claim and a non-sector-aligned byte total were rejected by the same production acceptance predicate.

## Known failure modes

The probe currently depends on a clean boot with an isolated formatted-card copy reaching menu audio; native saves should remove that temporary card precondition.
