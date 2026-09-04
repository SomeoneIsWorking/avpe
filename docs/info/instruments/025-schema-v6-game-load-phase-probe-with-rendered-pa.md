---
id: I025
kind: instrument
status: trusted
created: 2026-09-04
---

## Instrument

Schema-v6 game-load phase probe with rendered pause-menu selection, typed confirmation action, exact CProfile boundary, synchronous mission-goals completion, source-card preservation, and strict BIOS/IOP validation

## Validated by

The incompatible mission1-current/card pair produced the required negative with zero pacify/profile calls; omitting the mission-goals Exit left the boundary entered but incomplete; unit controls reject wrong menus, focus, action text, malformed boundaries, and source-card mutation; a real 2026-09-04 run observed three pacify calls, result zero, the 3609-cycle exact modal exit, 14444/14444 EE pairs, one identified blocking IOP receive at capture, and zero sequence errors or overflow

## Known failure modes

- The savestate and memory-card copy must describe the same live profile. An
  independently captured pair can expose a valid load menu yet reject the slot
  before the pacify boundary.
- The capture intentionally includes resumed mission initialization after the
  archive read. It cannot attribute each retained service to archive work.
- One blocking IOP call may remain pending at the exact guest completion
  boundary; sequence errors and overflow still fail the probe.
