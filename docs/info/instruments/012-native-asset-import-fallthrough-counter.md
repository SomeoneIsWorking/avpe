---
id: I012
kind: instrument
status: trusted
created: 2026-08-27
---

## Instrument

Native asset import-fallthrough counter exposed by the control-test trace

## Validated by

The same binary showed both answers: a no-store run recorded two original TBF fallthroughs and no native claims, while a validated-store run recorded native TBF/media lifecycles with zero original fallthrough and retained positive bootstrap fallthrough. Unit fixtures also reject missing oracle fallthrough and any native-path fallthrough.

## Known failure modes

The counter proves the import-dispatch branch, not the absence of unrelated optical work elsewhere in the emulator during the same wall-clock interval.
