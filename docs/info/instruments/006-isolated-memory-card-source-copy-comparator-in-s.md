---
id: I006
kind: instrument
status: trusted
created: 2026-08-27
---

## Instrument

isolated memory-card source/copy comparator in src/avpe/memory_card_probe.py

## Validated by

A unit fixture changed exactly byte 100 of the working copy and the instrument reported changed_bytes=1 with first/last offset 100 while preserving the source; a real surfaceless/null-muted five-second SLUS-20147 run against a copied formatted 8 MB card reported changed_bytes=0 and identical distinct source/working hashes, with the source hash rechecked after shutdown

## Known failure modes

(none recorded yet)
