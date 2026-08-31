---
id: C014
kind: claim
status: holds
created: 2026-08-27
tags: input,menu,mouse
depends: thirdparty/pcsx2/pcsx2/AVPE/NativeInputDispatch.cpp#QueuePointerMotion, thirdparty/pcsx2/pcsx2/AVPE/NativeMenuInput.cpp#MovePointer, thirdparty/pcsx2/pcsx2/AVPE/NativeMenuInput.cpp#MovePointerThroughDispatch, thirdparty/pcsx2/pcsx2/AVPE/NativeMenuInput.cpp#ActivatePointer, src/avpe/native_menu_pointer_dispatch_probe.py#probe_native_menu_pointer_dispatch, tools/run_control_test.py#probe_native_menu_pointer
---

## Claim

AVP:E native menu pointer motion uses game hit-testing to focus distinct items and pointer activation enters the focused item

## Evidence

The surfaceless/null-muted pause-menu probe moved the live callback-owned pointer 0x015FE940 to normalized (0.7,0.3) and (0.7,0.4); deferred GfsPointer::MenuCheck calls focused Resume 0x015DFB60 and Save 0x015E0640 respectively. A rejected x=1.25 request returned 400 and left deferred state unchanged. Deferred GfsPointer::Input_Action completed in 11373723 cycles with exact nonzero stack restoration and changed active menu 0x012E85A0 to 0x015AFA70; the runner shut down gracefully.

The Save Game menu does not safely return from the synchronous absolute-motion
path, so the diagnostic uses the registered `GAvPPointer::Input_UpdatePosition`
callback instead. Its measured `GMenuButton` center `(280,378)` focused
`0x015AFD10`; the original `GfsPointer::Input_Action` then completed through
the ordinary deferred scheduler with exact stack restoration. The earlier
`(431.33,178.80)` target is a `GMiner` render rectangle, not a menu item.

## What would falsify it

the pause-menu probe fails to focus two distinct nonzero game objects, a rejected coordinate queues or changes guest work, the Save Game dispatched probe fails to focus its measured button, or either focused activation fails exact stack restoration
