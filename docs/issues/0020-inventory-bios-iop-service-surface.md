---
id: 20
title: Inventory AVP:E BIOS and IOP service surface
status: investigating
symptom: The AVP:E-specific BIOS/HLE service surface is not yet inventoried
state_items: S025,S026,S027,S028
tags: bios,hle,iop,inventory,re
created: 2026-08-28
updated: 2026-08-28
---

## Root cause

Existing AVPE hooks observe selected asset imports and debug registrations, but
there is no bounded structured census covering the BIOS-backed IOP lifecycle,
and no corresponding EE-kernel or firmware-service inventory.

## Current work

`NativeBiosTrace` now records EE `SYSCALL` dispatches through the shared
interpreter implementation, including their four argument registers and
post-dispatch signed `v0` result, EE/IOP exception entry, plus IOP imports,
loadcore module registration and release, interrupt registration, and SIF RPC
registration. EE and IOP counter target/overflow paths now record the counter
state, cycle, and whether the interrupt was delivered. All observations use
narrow calls at the existing owners, remain observation-only, and are exposed at
`GET /bios/trace` for control-test diagnostics.

The surfaceless runner now captures the sink atomically at the verified
`Running` boundary through `POST /bios/trace/capture`. Three repeated clean
boots produced the same 28-event slice (20 module registrations, 7 IOP
exceptions, 1 IOP timer event, zero overflow), proving the boot boundary is
repeatable. The capture is deliberately labelled `clean_boot_to_running`; it
does not claim to cover later EE or game-service activity.

Successful savestate restoration is now an explicit phase boundary: the
standalone frontend resets the sink from `Host::OnSaveStateLoaded()` before the
emulation thread enters `Running`. The `title-real.p2s`, `pause-menu.p2s`, and
`mission1.p2s` resumes produced 220, 251, and 71 ordered events respectively,
all with zero overflow and different event mixes. This proves the bounded
instrument can observe post-restore execution without retaining the high-rate
restore-time scheduler burst.

The phase runner now has a reset/start boundary. A pause-menu `menu_down`
capture accepted the game's synchronous native action, and capture is aligned
to the emulation CPU thread. Two identical menu runs each produced 7 ordered
events (2 EE syscalls and 5 exceptions), with zero overflow. CPU-thread
save-load captures produced 34 and 31 ordered timer events, with zero
overflow. The latter proves post-load service traffic, while the save archive
itself remains a control-boundary observation rather than an invented BIOS
event claim.

The CPU-thread capture fixes the HTTP-versus-emulation ownership race for the
menu phase, but save-load event counts still vary. The archive restore callback
returns before a guest-owned completion/quiescence condition has been
identified. An arbitrary host delay would hide this boundary defect rather
than establish service semantics.

## Remaining work

Define and instrument guest-owned completion boundaries, then capture repeated
clean traces across boot, menu, mission, save, load, and
shutdown. Add a separate grounded observation seam for remaining interrupt
delivery, kernel primitives, executable loading, and IOP module loads, then
capture their service results and negative paths before designing the HLE
implementation. The EE syscall result boundary now exists but still needs
runtime phase traces and service-level interpretation.

## Resolution

Not resolved. The current census is the first partial S025 slice; it does not
establish a BIOS-free path or any S026–S028 behavior.
