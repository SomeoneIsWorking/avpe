---
id: 7
title: Profile creation fails before gameplay
status: investigating
symptom: The windowed product reaches profile creation but cannot create a profile, preventing entry into gameplay
state_items: S013,S014,S016
tags: profile,save,memory-card,playability
created: 2026-08-27
updated: 2026-08-27
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

## Resolution
