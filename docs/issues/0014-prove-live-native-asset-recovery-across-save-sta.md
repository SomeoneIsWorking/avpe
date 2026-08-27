---
id: 14
title: Prove live native asset recovery across save-state load
status: resolved
symptom: Native descriptor and synthetic CDVD mapping serialization builds and idle states load, but no runtime proof saves and reloads while native I/O ownership is live
state_items: S024
tags: assets,native-io,savestate,recovery
created: 2026-08-28
updated: 2026-08-28
---

## Root cause

The version-1 save-state schema records native descriptor slots/cursors and synthetic CDVD mappings, but the current runtime evidence saves only a clean boot state without proving either structure was active. Compile and idle-load evidence cannot detect restore ordering, slot, cursor, mapping, or admitted-identity defects on the live path.

## Acceptance

- The surfaceless/null-muted harness detects a live native ioman descriptor from production observations, saves through `/state/save`, reloads the same state through `/state/load`, and observes continued native reads with no original fallthrough.
- A separate synthetic-CDVD leg saves with a live STREAMS mapping, reloads it, and observes continued native sector reads plus matching native completion consumption.
- Both legs preserve admitted asset identity, report Running after load, leave completion/cache bounds valid, and keep the isolated source and working card hashes unchanged.
- The probe uses the shipping save/load and loader owners; copied fixtures or reimplemented serialization do not count.

### Resolution (2026-08-28)
Two separate surfaceless/null-muted clean runs proved live recovery through production save/load. INTRO.PSS restored exact fd/path/cursor and resumed reads without reopen/fallback; MENU01.ZIV restored exact mapping identity/LSN allocator and resumed sector reads plus completion consumption. Both isolated cards remained byte-identical; focused controls reject token, reopen, and snapshot-drift failures.
Strengthened reruns also reported Running after load and retained the exact
512-page/32 MiB cache bound with zero transient host handles.
