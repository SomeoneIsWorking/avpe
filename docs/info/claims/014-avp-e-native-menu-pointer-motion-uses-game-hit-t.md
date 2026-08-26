---
id: C014
kind: claim
status: holds
created: 2026-08-27
tags: input,menu,mouse
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeMenuInput.cpp#MovePointer, thirdparty/pcsx2/pcsx2/AVPE/NativeMenuInput.cpp#ActivatePointer, tools/run_control_test.py#probe_native_menu_pointer
---

## Claim

AVP:E native menu pointer motion uses game hit-testing to focus distinct items and pointer activation enters the focused item

## Evidence

The surfaceless/null-muted pause-menu probe moved the live callback-owned pointer 0x015FE940 to normalized (0.7,0.3) and (0.7,0.4); deferred GfsPointer::MenuCheck calls focused Resume 0x015DFB60 and Save 0x015E0640 respectively. A rejected x=1.25 request returned 400 and left deferred state unchanged. Deferred GfsPointer::Input_Action completed in 11373723 cycles with exact nonzero stack restoration and changed active menu 0x012E85A0 to 0x015AFA70; the runner shut down gracefully.

## What would falsify it

the pause-menu probe fails to focus two distinct nonzero game objects, a rejected coordinate queues or changes guest work, activation fails exact stack restoration, or the focused activation fails to change the active game-owned menu
