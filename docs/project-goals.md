# AVPE project goals

Goals are epic-level product intent. Factual capability coverage lives in
[`project-state.md`](project-state.md), atomic work in [`issues/`](issues/),
and code ownership in [`codemap.md`](codemap.md).

## G001 — Desktop AVPE product

**Outcome.** A user who supplies a legally obtained *Aliens Versus Predator:
Extinction* disc image and PS2 BIOS can provision and launch the current PC
product through `./run.sh` on a supported desktop system.

**Why.** The project exists to make AVP:E directly usable as a maintained PC
experience rather than a collection of reverse-engineering experiments.

**Success conditions.** The zero-argument launcher provisions portable inputs,
builds the maintained PCSX2 fork and AVPE host when needed, and opens the
windowed product in an AVPE-owned host shell. That shell owns the visible
window, input focus, product menus, and presentation lifecycle; PCSX2's generic
main window, render window, and emulator settings UI are not exposed in the
normal product. The documented native dependencies, a compatible C++ compiler,
`uv`, and the user-supplied game/BIOS assets are sufficient; Ghidra and other
maintainer-only RE tools are not runtime or build prerequisites.

**Related state items.** S001, S003–S006, S012–S013, S020.

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
- Copyrighted game and BIOS assets remain user supplied and untracked.
- The normal user launch is windowed through the AVPE shell. Surfaceless,
  timeboxed, and HTTP-controlled modes are developer/agent interfaces and are
  never routed through `run.sh`.
- Unrelated general-purpose PCSX2 features are outside this project's goals.
