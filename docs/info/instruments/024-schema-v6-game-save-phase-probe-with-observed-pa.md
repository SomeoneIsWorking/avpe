---
id: I024
kind: instrument
status: trusted
created: 2026-09-04
---

## Instrument

Schema-v6 game-save phase probe with observed pad lifecycle, CPU-thread memory-card readiness, exact menu callback dispatch, grounded CProfile boundary, and strict BIOS/IOP pairing validation

## Validated by

Old save-menu fixtures produced the required negative with zero pacify calls and no boundary; unit controls reject missing press/release, card auto-eject, busy card, wrong callback owner vtable, malformed result summaries, and mismatched pairing; a real 2026-09-04 run observed card auto-eject and busy states, three pacify calls, result zero, source-card preservation, working-card mutation, 3396/3396 EE and 340/340 IOP pairs, and zero overflow

## Known failure modes

- The evidence depends on the supplied state and memory card representing the
  same live profile; another independently captured pair is not interchangeable.
- A bounded control-test deadline can expire under severe host contention
  before the guest reaches a completion boundary; such a run produces no
  semantic evidence.
- The probe establishes one normal save service slice. It does not prove the
  complete firmware inventory, the load/shutdown paths, or a native-save backend.
