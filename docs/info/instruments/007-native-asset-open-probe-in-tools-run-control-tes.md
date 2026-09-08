---
id: I007
kind: instrument
status: trusted
created: 2026-08-27
---

## Instrument

Native asset-open probe in tools/run_control_test.py and AVPE::NativeAssets

## Validated by

A real SLUS-20147 CRC 64DA78A3 surfaceless/null-muted boot produced 20 total
and 16 unique IOP open observations including native TBF.TBF, boot-time TBX/TBD
refusals with guest result -2, and the deliberately absent
__avpe_absent_asset__ sentinel at zero; unit fixtures also reject empty and
sentinel-contaminated traces

## Known failure modes

(none recorded yet)
