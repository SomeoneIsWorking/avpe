---
id: C016
kind: claim
status: holds
created: 2026-08-27
tags: save,profile,re
---

## Claim

AVP:E's normal profile and game-save boundary is CProfile, with a 0x118-byte outer record, multi-file profile provisioning, fixed profile payload, and BWJ-compressed game-object saves

## Evidence

SLUS-20147 symbol inventory and targeted Ghidra decompilation identify CProfile functions 0x0012FAA0-0x00130800, CProfileDef creation at 0x0012F4A0-0x0012F7F0, CZFile memory-card flags, literal BASLUS-20147%08X and numbered .SAV paths, exact 0x118 record reads/writes, 0x20 level-name write, CLoadSaveBuffer compression, and 0x7E400 slot padding; docs/re/save-path.md records the field-level derivation

## What would falsify it

a runtime trace shows normal profile or game saves bypassing CProfile, a deliberately differing valid record contradicts the recorded outer layout, or a save produced through these functions cannot be loaded by the original game
