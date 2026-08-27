---
id: C028
kind: claim
status: holds
created: 2026-08-28
tags: assets,savestate,recovery
depends: thirdparty/pcsx2/pcsx2/IopBios.cpp, thirdparty/pcsx2/pcsx2/AVPE/NativeAssetStateSnapshot.cpp#CaptureJsonOnCPUThread, src/avpe/native_asset_probe.py#probe_native_ioman_state_recovery, src/avpe/native_asset_probe.py#probe_native_cdvd_state_recovery
---

## Claim

Live AVP:E native descriptors and synthetic CDVD mappings survive production save-state round trips and resume native reads without reopening or optical fallback

## Evidence

Two clean surfaceless/null-muted runs used the shipping /state/save and /state/load routes. INTRO.PSS restored at fd 257/cursor 131072 and then advanced observed bytes from 147456 to 393216 without a reopen. MENU01.ZIV restored exact path/base LSN 3758096384/size 7602176/SHA-256/next LSN 3758100096 and then advanced observed bytes from 65536 to 131072 plus matching completion consumption from three to four. Both runs had zero active/rejected completion tokens, zero target fallback, and byte-identical isolated cards.

Strengthened reruns also required the post-load endpoint to report Running,
surfaceless, and null-muted, and required a bounded cache snapshot with zero
transient host handles. Both passed; the descriptor run observed 475/512 pages,
and the CDVD run exercised the exact 512-page bound with eviction.

## What would falsify it

A clean admitted-store round trip changes any saved native descriptor fd/path/cursor or CDVD path/base-LSN/size/SHA-256/next-LSN, crosses an active completion token, reopens or falls back for the restored target, fails to resume native reads/completion, or changes the isolated card
