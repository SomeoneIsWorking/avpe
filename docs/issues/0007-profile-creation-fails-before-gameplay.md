---
id: 7
title: Profile creation fails before gameplay
status: investigating
symptom: The windowed product reaches profile creation but cannot create a profile, preventing entry into gameplay
state_items: S013,S014,S016
tags: profile,save,memory-card,playability
created: 2026-08-27
updated: 2026-08-29
---

## Root cause

Not yet isolated. Profile creation is not one card write: the game creates the
profile directory and outer record, then provisions four padded save slots,
`List.ico`, `blart.dat`, and `icon.sys`. The product card contains the generated
`BASLUS-20147F991C326` directory string and `Extinction 1`, so the initial
creation path reached persistent storage and a later stage or subsequent menu
transition may be the failing operation.

## What was tried / dead ends

Static analysis mapped the complete high-level `CProfile` boundary and outer
record in [`../re/save-path.md`](../re/save-path.md). The isolated control runner
now accepts `--memory-card-source`, works only on a copied card, and reports
byte changes. No symptom-only patch has been applied to the legacy memory-card
path because G003 replaces that path with native saves.

### Finding (2026-08-29)

The available ignored source card contains one valid profile record and its
fixed 0x20-byte payload. The observed display name is `Extinction 1`, the
directory is `BASLUS-20147F991C326`, and the record fields are documented in
[`../re/save-path.md`](../re/save-path.md). This is a live payload/default
observation, not the deliberately differing pair required to resolve the
unknown fields; the card contains no grounded pair of differing game saves.

### Finding (2026-08-29, runtime owner)

A BIOS-backed pause-menu state exposed the live `CProfile` instance and its
`SetGameData` fields: object `0x003B2620`, payload `0x003D6A40`, size `0x20`,
revision `0x1CD9DEE3`, and four save targets. A direct diagnostic call to
`CProfile::SaveProfile` exceeded the 3,000,000-cycle shuttle budget and was
recovered by loading the known state. This is evidence that the save routine
must be exercised through its normal game path; it is not evidence that the
card write itself failed.

## Resolution
