# AVPE project goals

Goals are epic-level product intent. Factual capability coverage lives in
[`project-state.md`](project-state.md), atomic work in [`issues/`](issues/),
and code ownership in [`codemap.md`](codemap.md).

## G001 — Desktop AVPE product

**Outcome.** A user who supplies a legally obtained *Aliens Versus Predator:
Extinction* disc image can provision and launch the current PC product through
`./run.sh` on a supported desktop system without supplying console firmware.

**Why.** The project exists to make AVP:E directly usable as a maintained PC
experience rather than a collection of reverse-engineering experiments.

**Success conditions.** The zero-argument launcher provisions portable inputs,
builds the maintained PCSX2 fork and AVPE host when needed, and opens the
windowed product in an AVPE-owned host shell. That shell owns the visible
window, input focus, product menus, and presentation lifecycle; PCSX2's generic
main window, render window, and emulator settings UI are not exposed in the
normal product. The documented native dependencies, a compatible C++ compiler,
`uv`, and the user-supplied game assets are sufficient; Ghidra and other
maintainer-only RE tools are not runtime or build prerequisites.

**Related state items.** S001, S003–S006, S012–S013, S020, S027.

## G002 — Native PC RTS control

**Outcome.** Menus and gameplay use a native keyboard-and-mouse control scheme
modeled on established PC RTS conventions, with StarCraft as the primary
interaction reference, routed into AVP:E's own input, pointer, selector,
camera, and command systems.

**Why.** A PC port should expose PC-native controls and preserve the game's
semantics instead of presenting keyboard/mouse as a virtual DualShock wrapper.

**Success conditions.** Absolute cursor motion, left-click and drag selection,
right-click contextual commands, keyboard shortcuts, camera movement, minimap
behavior, selector-mode changes, and every normal game menu (title, mission,
pause, and in-game) behave coherently with keyboard and mouse as a PC RTS and
are dynamically verified against the running game. The reference supplies
interaction conventions, not copied StarCraft assets, code, or game rules.

**Related state items.** S002, S005–S011, S013.

## G003 — PC-native saves

**Outcome.** AVP:E progress is stored as ordinary PC save files owned by the
port, without exposing a virtual PS2 memory-card image or memory-card management
UI in the normal product path.

**Why.** Saves are durable user data. A PC product should give them explicit,
portable ownership, atomic persistence, and actionable failures rather than
embedding them in an opaque emulated-card container.

**Success conditions.** The game's save/load boundary and on-card schema are
grounded from the executable and real save data; profiles, slots, settings, and
autosave data round-trip through a versioned native backend; writes are atomic
and recoverable; corrupted or incompatible data is refused by name; a clean
restart loads the same progress; and existing AVP:E memory-card progress has a
one-time import path into the native representation.

**Related state items.** S014–S017.

## G004 — Native options and display configuration

**Outcome.** AVPE exposes a project-owned native options surface built with
RmlUi, including graphics, display mode, and resolution controls appropriate
to a desktop game.

**Why.** Product settings should be discoverable inside AVPE and expressed in
game-facing language rather than requiring users to navigate PCSX2's general
emulator interface or edit configuration files.

**Success conditions.** The RmlUi surface opens from the normal product path,
enumerates supported display choices, applies graphics and resolution changes
through their authoritative PCSX2 owners, persists them in project-owned
configuration, reports rejected combinations clearly, and restores the same
choices after a clean restart. Keyboard and mouse navigation work without the
diagnostic control client.

**Related state items.** S018–S020.

## G005 — PC-native asset I/O

**Outcome.** Normal AVP:E asset loading reads directly from native PC storage
instead of traversing the emulated PS2 optical-disc request, seek, and transfer
stack.

**Why.** Optical-drive latency and the many layers needed to reproduce it are
console constraints, not desirable PC behavior. Collapsing that path into
native file reads should make mission and transition loading substantially
faster while keeping the game's asset semantics intact.

**Success conditions.** The executable's disc/file access boundary and asset
namespace are grounded; user-supplied disc content is provisioned into a
validated native asset store; normal game asset requests resolve through a
project-owned host I/O layer with bounded asynchronous reads and caching; byte
content, ordering, short-read, missing-file, and failure behavior remain
compatible with the game; and representative cold and warm loading sequences
are measurably faster than the emulated-disc baseline. After bootstrap, the
normal product path does not depend on emulated optical seeks or sector-timed
transfers for supported game assets.

**Related state items.** S021–S024.

## G006 — AVP:E-specific HLE BIOS

**Outcome.** AVPE boots and runs the supported game revision through a
project-owned high-level implementation of the PS2 firmware and platform
services it actually uses, without requiring a user-supplied retail BIOS.

**Why.** A PC-native release should not depend on opaque copyrighted console
firmware when the target's required service contract can be implemented and
verified directly. Limiting the HLE surface to AVP:E keeps the work grounded
and avoids pretending to provide a general PS2 BIOS replacement.

**Success conditions.** Every BIOS syscall, kernel primitive, interrupt/timer
behavior, executable-loader operation, and IOP/module service reached by the
supported target is inventoried with positive and negative traces; a clean-room
HLE implementation supplies those contracts deterministically; the game boots,
loads missions, saves, and completes representative play sequences with no
retail BIOS bytes present; unimplemented or divergent services fail by exact
name; and the normal product cannot silently fall back to external firmware.
Behavior is compared against the current BIOS-backed oracle until each required
service is grounded.

**Related state items.** S025–S028.

## Constraints and non-goals

- The product is an AVPE-owned native host shell backed by a maintained PCSX2
  fork plus project integration; static recompilation is not the selected
  architecture.
- Shipping keyboard/mouse control directly drives game-native structures and
  functions. Pad injection may remain a diagnostic/bootstrap instrument, not
  the finished input architecture.
- StarCraft is a control-design reference only; AVPE does not reproduce its
  copyrighted presentation, assets, code, or title-specific mechanics.
- RmlUi owns the native options presentation. Existing PCSX2 graphics, display,
  and persistence subsystems remain authoritative for the settings themselves.
- Native saves replace AVP:E's memory-card dependency only. A generic PS2
  memory-card manager or save backend for unrelated games is out of scope.
- PC-native asset I/O replaces AVP:E's normal game-data reads only. Copyrighted
  content remains derived from the user's own disc image and is never committed
  or distributed by the project.
- The HLE BIOS is a clean-room, AVP:E-specific platform-service implementation.
  General PS2 software compatibility and redistribution of Sony firmware are
  explicit non-goals.
- Copyrighted game and BIOS assets remain user supplied and untracked.
- The normal user launch is windowed through the AVPE shell. Surfaceless,
  timeboxed, and HTTP-controlled modes are developer/agent interfaces and are
  never routed through `run.sh`.
- Unrelated general-purpose PCSX2 features are outside this project's goals.
