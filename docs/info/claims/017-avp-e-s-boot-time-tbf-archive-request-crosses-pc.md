---
id: C017
kind: claim
status: holds
created: 2026-08-27
tags: assets,ioman,re
depends: thirdparty/pcsx2/pcsx2/IopBios.cpp#open_HLE, thirdparty/pcsx2/pcsx2/AVPE/NativeAssets.cpp#ObserveIomanOpen
---

## Claim

AVP:E's boot-time TBF archive request crosses PCSX2's ioman import HLE boundary before the original IOP handler and can be observed without claiming the request

## Evidence

Static interpreter/recompiler import-hook inspection plus the 2026-08-27 surfaceless/null-muted SLUS-20147 CRC 64DA78A3 run recorded two cdrom0:/TBD/TBF.TBF;1 opens while the observer always returned to the original implementation; docs/re/disc-io.md

## What would falsify it

a supported boot loads TBF.TBF without a corresponding ioman/iomanX open at this hook, or enabling the observation-only seam changes the original request result
