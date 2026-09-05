# AVPE

AVPE is a reverse-engineering-driven PC game port of *Aliens Versus
Predator: Extinction* (PS2). It combines a maintained PCSX2 fork with an
AVPE-owned host frontend and native PC input and asset-I/O work.

## Current status

This repository is public, but the product is still in development. Today,
you must provide both a legally obtained AVP:E game image and a compatible
PS2 BIOS. The BIOS-free HLE target is not implemented, and the end-to-end
windowed product has not yet been verified.

The currently verified capabilities include:

- locked Python/`uv` project setup and a tracked PCSX2 fork;
- a surfaceless, null-audio control-test runtime with loopback diagnostics;
- game-native absolute pointer movement, mouse selection, contextual commands,
  pause-menu navigation, title-to-profile activation without controller
  emulation, and camera/minimap probes (verified through the surfaceless backend);
- validated native asset-store provisioning from the user’s disc image;
- native reads for the supported AVP:E asset paths, with byte and loading-time
  evidence against the emulator’s optical-I/O path; and
- grounded investigation of the AVP:E save boundary and BIOS/IOP service
  surface.

The following remain incomplete: full real-window keyboard/mouse delivery and
playability, complete menu coverage, PC-native saves and memory-card import,
project-owned options, and the AVP:E-specific BIOS/HLE implementation. The
authoritative capability inventory is [`docs/project-state.md`](docs/project-state.md);
epic intent is in [`docs/project-goals.md`](docs/project-goals.md).

## Requirements

The supported development path currently targets Linux and macOS and requires:

- `uv`;
- a C++ compiler (GCC, Clang, or AppleClang), CMake, Ninja, and `ccache`;
- `git`, `bash`, `curl`, `make`, `patch`, `gzip`, `tar`, and `shasum` for
  dependency provisioning;
- `pkg-config`, SDL3 development files, and MAME’s `chdman` utility; and
- the user-supplied AVP:E CHD and PCSX2 BIOS directory.

The launcher provisions the project’s Qt/dependency prefix under ignored
`build/deps/` when needed. It does not install system packages or copyrighted
assets. If a native dependency is missing, `doctor` reports the missing name
and a platform-specific command for the user to run. Windows is not currently
an automatic provisioning target.

## Fresh checkout

1. Install the requirements above, including `uv` and the native packages for
   your operating system.
2. Create the local asset configuration:

   ```sh
   cp .env.example .env
   ```

3. Edit `.env` so the paths name your own files:

   ```text
   AVPE_CHD=/path/to/Aliens Versus Predator - Extinction (USA).chd
   AVPE_BIOS_DIR=/path/to/PCSX2/bios
   ```

4. Check the machine and asset prerequisites:

   ```sh
   ./run.sh doctor
   ```

5. Prepare the tracked submodule, dependency prefix, and AVPE executable:

   ```sh
   ./run.sh prepare
   ```

The CHD and BIOS files must remain outside version control. Derived asset
bytes are kept under ignored `scratch/` directories; generated build outputs
belong under ignored `build/`.

## Running AVPE

The zero-argument command is the product launcher:

```sh
./run.sh
```

It prepares the current AVPE target when necessary, validates/provisions the
native asset store from `AVPE_CHD`, and starts the standalone AVPE host. The
explicit equivalent is:

```sh
./run.sh launch
```

Useful setup commands are:

```sh
./run.sh provision   # initialize or repair the tracked PCSX2 submodule
./run.sh prepare     # build without launching the product
./run.sh assets      # validate/provision native assets only
```

The diagnostic runner is a separate maintainer interface and is intentionally
not hidden behind `run.sh`:

```sh
uv run --frozen python tools/run_control_test.py --seconds 30
```

It uses a surfaceless, null-muted process and isolated state. See
[`docs/re/headless.md`](docs/re/headless.md) before using its probes.

## Project layout

- `src/avpe/` — locked launcher orchestration, provisioning, asset validation,
  and diagnostic probe policy;
- `thirdparty/pcsx2/pcsx2-avpe/` — standalone AVPE frontend and host shell;
- `thirdparty/pcsx2/pcsx2/AVPE/` — AVP:E-specific emulator integration and
  native subsystem owners;
- `tools/` — Python project tooling and control clients; and
- `docs/` — goals, factual state, ownership map, reverse-engineering notes,
  claims, instruments, and atomic issues.

The ownership boundaries are documented in [`docs/codemap.md`](docs/codemap.md)
and the project-specific rules are in [`AGENTS.md`](AGENTS.md).

## Contributing and evidence

Changes should preserve the project’s evidence-first workflow. Before adding a
new path, consult the project registries and identify the owning subsystem;
keep host composition, platform events, input policy, game behavior, storage,
and diagnostics in separate modules. Do not commit ROMs, disc images, BIOS
files, extracted game data, or machine-specific paths.

For behavior changes, include positive and negative tests at the production
boundary, record reproducible evidence in the nearest `docs/` authority, and
update `docs/project-state.md` only when an observable capability actually
changes. Claims must state what would falsify them. Maintainer verification
uses the locked environment and the repository’s normal verifier:

```sh
uv run --frozen python tools/verify.py
```

Detailed reverse-engineering and runtime artifacts belong under ignored
`scratch/`, not in the public repository. Copyrighted source material and
console firmware are not distributed here.
