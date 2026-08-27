---
id: I016
kind: instrument
status: trusted
created: 2026-08-28
---

## Instrument

NativeAssetCache production tests plus surfaceless bounded-cache probe

## Validated by

A failed fill installed zero pages and a retry succeeded; a 513-page run evicted the true LRU at the exact 32 MiB cap; the live TBF probe observed both misses and hits, one peak transient handle, and zero handles after reads.

## Known failure modes

(none recorded yet)
