---
id: 20
title: Inventory AVP:E BIOS and IOP service surface
status: investigating
symptom: The AVP:E-specific BIOS/HLE service surface is not yet inventoried
state_items: S025,S026,S027,S028
tags: bios,hle,iop,inventory,re
created: 2026-08-28
updated: 2026-08-29
---

## Root cause

Existing AVPE hooks observe selected asset imports and debug registrations, but
there is no bounded structured census covering the BIOS-backed IOP lifecycle,
and no corresponding EE-kernel or firmware-service inventory.

## Current work

`NativeBiosTrace` now records EE `SYSCALL` dispatches through the shared
interpreter implementation, including their four argument registers and
post-dispatch signed `v0` result, EE/IOP exception entry, plus recognized HLE/
debug IOP imports,
loadcore module registration and release, interrupt registration, and SIF RPC
registration. EE and IOP counter target/overflow paths now record the counter
state, cycle, and whether the interrupt was delivered. All observations use
narrow calls at the existing owners, remain observation-only, and are exposed at
`GET /bios/trace` for control-test diagnostics. Repeated import, syscall,
exception, and timer identities are coalesced with occurrence counts; unknown
import-looking probes remain on the original oracle path.

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

Phase capture now has a narrower boundary: the control route can arm the sink
and wait for the next `Counters::VSyncStart` transition on the emulation CPU
thread. Two repeated pause-menu captures through that route remained bounded
with zero overflow but retained 21 and 11 event identities, with different
exception/syscall identity sets. This removes the control request's frame
position race, but the differing traces show that a frame transition is not
the guest-owned post-restore completion boundary still needed for repeatable
mission/save/load inventory.

The retained trace set is now mechanically summarized by
`tools/analyze_bios_traces.py`, which reuses the runner's strict validator and
groups only events actually present in each capture. The selected seven
captures contain 335 events across clean boot, title resume, menu, and
save-load phases. Their runtime service categories are EE syscalls and module
registration; IOP import, interrupt-registration, and RPC events are absent
from these windows even though their encodings remain covered by production
tests.

The observed EE syscall identities in the retained set are
`RotateThreadReadyQueue` (#43), `sceSifSetDma_isceSifSetDma` (#119),
`sceSifSetDChain_isceSifSetDChain` (#120), `iSignalSema` (#67), `RFU005` (#5),
`DeleteSema` (#65), `CreateSema` (#64), and `WaitSema` (#68). The set includes
both `RotateThreadReadyQueue` results 0 and 1, plus `DeleteSema` result 11;
other observed returns are zero except for the dynamic `WaitSema` results.
This is a service-level observed subset, not the complete syscall inventory.

### Finding (2026-08-29, mission-state repeatability control)

Two fresh `mission1.p2s` statefile-to-running captures were both accepted as
bounded traces, but the first contained 237 events (2 EE syscalls, 84
exceptions, and 151 timers) and the immediate repeat contained only one timer
event. This is negative repeatability evidence: the state-restore callback and
capture route still do not define a guest-owned completion/quiescence boundary.
The traces must not be combined into a claimed mission-service inventory.

### Finding (2026-08-29, clean stream import census)

The first recompiler change routed every import-looking `addiu` through the
interpreter dispatcher and produced 54 million dropped trace events during a
clean stream probe. Static inspection and live snapshots separated the causes:
unhandled import-looking probes, then hot EE exception/syscall and timer
repetition. The final narrow implementation keeps the existing recompiler HLE
and debug path, admits only recognized HLE/debug imports, and coalesces repeated
identities in the observation sink. A Clang-built clean-boot native stream
probe then completed with 11 recognized import identities, including
`ioman.read` and `cdvdman` read/seek/getError/searchFile, 1,290 retained event
identities, and zero overflow. The native stream proof also recorded two
completed `MENU01.ZIV` sector reads.

### Finding (2026-08-29, static EE syscall candidates)

`tools/analyze_ee_syscalls.py` now scans executable PT_LOAD code from the
user-supplied ELF without tracking the asset. On `SLUS_201.47` it found one
executable segment, 158 embedded BIOS wrapper definitions, 458 direct wrapper
callsites, and 8 direct syscall instructions, covering 63 statically decoded
syscall numbers. The scanner keeps static candidates separate from runtime
observations and cannot see indirect or data-driven dispatch; it therefore
narrows the next runtime inventory but does not establish service execution or
results.

### Finding (2026-08-29, grounded mission boundary seam)

The BIOS phase runner now waits for the existing native `MENU01.ZIV`
readiness boundary, arms a one-shot observer through the shared EE execution
instrumentation, and pairs `CShell::ShellLoadLevel` entry `0x0016F910` with
the first post-load point `0x0016FA4C`. It records the two guest clocks,
frame, ordinal, and host time, rejects wrong ordering or duplicate points, and
returns a bounded refusal when the return is absent. A 180-second Clang-built
clean-boot run reached native `MENU01` readiness and the M1 trigger, but the
mission capture returned HTTP 504 because the grounded return was not observed
within its five-second deadline. The seam is therefore exercised but no
mission boundary or service-level runtime claim is accepted.

## Remaining work

Use the new grounded `CShell::ShellLoadLevel` boundary at `0x0016FA4C` to
capture repeated clean traces once the return is observed, then cover boot,
menu, mission, save, load, and
shutdown. Add a separate grounded observation seam for remaining interrupt
delivery, kernel primitives, executable loading, and IOP module loads, then
capture their service results and negative paths before designing the HLE
implementation. The EE syscall result boundary now exists but still needs
runtime phase traces and service-level interpretation.

## Resolution

Not resolved. The current census is the first partial S025 slice; it does not
establish a BIOS-free path or any S026–S028 behavior.
