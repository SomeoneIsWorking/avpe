---
id: I020
kind: instrument
status: DISTRUSTED
created: 2026-08-30
distrusted_on: 2026-08-30
---

## Instrument

NativeBiosTrace v2 service outcome/result-validity sink plus bios_trace_is_verified and bios_inventory analyzer

## Validated by

Native unit tests forced BIOS/oracle events to omit results and direct/HLE events to retain results; three clean mission artifacts contained both HLE-valid and BIOS/oracle-unobserved outcomes with no malformed result fields, and the analyzer preserved each class separately.

## Known failure modes

- The EE syscall seam observes BIOS entry, not BIOS return; `result_valid=false`
  is an explicit unobserved result, not a successful zero return.
- IOP oracle fallbacks likewise have no result at this seam.
- Coalesced events retain only the first argument vector for their
  identity/outcome/result group.
- Exact BIOS syscall call totals can vary with scheduling; three matched mission
  captures differed by one `sceSifSetDma` call.

## DISTRUSTED 2026-08-30

The v2 validator equates direct ownership with a valid result, but GetOsdConfigParam2 returns directly without assigning v0; the ix86 constant FlushCache/iFlushCache path also bypasses the observer. The instrument demonstrated BIOS/oracle omission correctly in the mission slice but cannot be trusted for all direct EE syscall paths.

> Every result this instrument produced is suspect until it is re-validated.
