---
id: C016
kind: claim
status: holds
created: 2026-08-27
tags: save,profile,re
depends: docs/re/save-path.md
reconfirmed: 2026-08-29
verified_at: 2026-08-29 00:01:12
---

## Claim

AVP:E's normal profile and game-save boundary is CProfile, with a 0x118-byte outer record, multi-file profile provisioning, fixed profile payload, and BWJ-compressed game-object saves

## Evidence

SLUS-20147 symbol inventory and targeted Ghidra decompilation identify CProfile functions 0x0012FAA0-0x00130800, CProfileDef creation at 0x0012F4A0-0x0012F7F0, CZFile memory-card flags, literal BASLUS-20147%08X and numbered .SAV paths, exact 0x118 record reads/writes, 0x20 level-name write, CLoadSaveBuffer compression, and 0x7E400 slot padding; docs/re/save-path.md records the field-level derivation

## What would falsify it

a runtime trace shows normal profile or game saves bypassing CProfile, a deliberately differing valid record contradicts the recorded outer layout, or a save produced through these functions cannot be loaded by the original game

## Re-confirmed 2026-08-29

The ignored user-supplied scratch/control-test/source-card.ps2 contains one profile file record with 0x118-byte outer record plus 0x20-byte payload: display Extinction 1, directory BASLUS-20147F991C326, CRC 0xF991C326, revision 0x1CD9DEE3, payload-size field 0x20, and record SHA-256 7b53c401b617cfbabe5729f3584303c6fd72b48f19ad47bdf33d48e99a89eb4f. This confirms one live record at the documented CProfile boundary; it does not claim differing profile/game-save coverage.
