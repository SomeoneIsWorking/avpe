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
builds the maintained PCSX2 fork when needed, and opens the windowed product.
The documented native dependencies, a compatible C++ compiler, `uv`, and the
user-supplied game/BIOS assets are sufficient; Ghidra and other maintainer-only
RE tools are not runtime or build prerequisites.

**Related state items.** S001, S003–S006, S012–S013.

## G002 — Native keyboard and mouse control

**Outcome.** Menus and gameplay are controllable with native keyboard and mouse
input routed into AVP:E's own input, pointer, selector, camera, and command
systems.

**Why.** A PC port should expose PC-native controls and preserve the game's
semantics instead of presenting keyboard/mouse as a virtual DualShock wrapper.

**Success conditions.** Absolute cursor motion, selection, command clicks,
menus, camera movement, minimap behavior, and selector-mode changes work
end-to-end and are dynamically verified against the running game.

**Related state items.** S002, S005–S011, S013.

## Constraints and non-goals

- The product is a maintained PCSX2 fork plus project-owned integration; static
  recompilation is not the selected architecture.
- Shipping keyboard/mouse control directly drives game-native structures and
  functions. Pad injection may remain a diagnostic/bootstrap instrument, not
  the finished input architecture.
- Copyrighted game and BIOS assets remain user supplied and untracked.
- The normal user launch is windowed. Headless, timeboxed, and HTTP-controlled
  modes are developer/agent interfaces.
- Unrelated general-purpose PCSX2 features are outside this project's goals.
