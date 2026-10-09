# AVPE project state

Factual capability inventory. Epic intent is in
[`project-goals.md`](project-goals.md), atomic work in [`issues/`](issues/), and
ownership in [`codemap.md`](codemap.md).

`verified` — observed working. `partial` — named subset works, gap named.
`blocked` — named item prevents completion. `missing` — absent.

**Current focus:** S025 — finish the required firmware service inventory, then
close S029 (PC-native prompts) and S013 (playable windowed product).

| id | capability | state | evidence or gap |
|---|---|---|---|
| S001 | Preflight, user-asset discovery, disc conversion | verified | `avpe doctor`, `.env.example`, `src/avpe/cli.py`, `tools/raw2352.py` |
| S002 | Game-native input and pointer map | verified | `docs/re/input-path.md` |
| S003 | Maintained PCSX2 fork builds the AVPE integration | verified | tracked gitlink + `deps.toml`; builds through `avpe prepare` |
| S004 | Surfaceless, silent control-test boot | verified | `tools/run_control_test.py` with offscreen Qt and null audio |
| S005 | Live control channel (status, EE memory, savestate, input, snapshot) | verified | `docs/re/control-channel.md`; `tools/avpe_http.py` |
| S006 | Reproducible mission state and located live cursor | verified | control-test mission state + `GMarinePointer` address |
| S007 | Reusable VM-thread EE-call shuttle | verified | fork-local `EECallShuttle`; fails closed on cycle budget |
| S008 | Native absolute pointer injection moves the cursor | verified | `NativeInput::MoveAbsolute` renders through guest input |
| S009 | Native mouse selection and command clicks | verified | original four mouse handlers invoked; Audio-menu buttons work |
| S010 | Keyboard and mouse menu navigation | partial | pause-menu navigation verified; product-window delivery and full menu coverage open (issue #6) |
| S011 | Selector, camera, minimap, pointer-mode integration | partial | `Input_GPMove/Rotate/Zoom` invoked; no live selector-mode or minimap proof (issue #19 resolved, camera only) |
| S012 | Fresh-clone provisioning through the zero-argument launcher | partial | submodule + deps prefix + target build automated; Ghidra-class RE prerequisites and platform gaps remain (issue #18) |
| S013 | End-to-end windowed product playable with PC RTS controls | blocked | needs S009–S012 and S020; requires a clean windowed run through menus, selection, commands, camera, minimap |
| S014 | AVP:E save/load boundary and on-card schema | partial | `CProfile` create/load/save/list boundary and record layout grounded; editable field semantics unproven |
| S015 | Atomic versioned PC-native save backend | partial | `src/avpe/native_save_store.py` container; game path does not yet use it end to end |
| S016 | Game save/load without a virtual PS2 memory card | blocked | needs S014 and S015; no card UI or card-format prompt may be reachable |
| S017 | Existing memory-card progress imports into native saves | partial | `src/avpe/memory_card_import.py` reads the card superblock/FAT; slot coverage unproven |
| S018 | Desktop options integrated into AVP:E's own menus | missing | AVP:E exposes no project-owned graphics/display/resolution entries |
| S019 | Graphics, display, and resolution settings apply and persist | blocked | blocked by S018; needs mode enumeration and rejected-choice refusal |
| S020 | AVPE-owned host shell owns window and presentation | partial | standalone `avpe` links the core with no PCSX2 main window; surface lifecycle not fully verified (issue #3) |
| S021 | AVP:E disc/file access boundary and asset namespace mapped | verified | `CZFile`/`CZRiffFile`/`CTbdFile` path grounded in `docs/codemap.md` |
| S022 | User disc provisions a validated native asset store | verified | `avpe assets`; exact `SYSTEM.CNF`, `SLUS_201.47`, `TBD/TBF.TBF` anchors |
| S023 | Supported asset requests use native storage, not emulated optical I/O | verified | `NativeAssetStore` + manifest SHA-256 admission; TBF, movies, FSSOUND streams |
| S024 | Native asset I/O preserves behavior and cuts loading time | verified | canonical-chunk match against the ISO oracle; fallthrough counter and timing evidence in `scratch/` |
| S025 | Required BIOS, kernel, and IOP service surface inventoried | partial | bounded census at `GET /bios/trace` with paired EE BIOS and IOP oracle returns; title completion, shutdown, and negative paths absent (issue #20) |
| S026 | Clean-room AVP:E-specific HLE service implementation | blocked | blocked by S025; needs success, error, timing, ordering, and loud refusal of unknown services |
| S027 | Supported target boots and runs without retail BIOS bytes | blocked | blocked by S026 |
| S028 | HLE behavior differentially verified against the BIOS oracle | blocked | blocked by S025 and S026 |
| S029 | Product prompts name PC actions instead of PS2 buttons | partial | every `MASTER.TBD` glyph-mesh prompt is covered by a key cap keyed by its drawing item (Enter confirm, Esc back, label letter for other commands, as in a PC RTS) at the VU1-placed rect; live placement and keys verified in the M1 pause menu; key caps seen in the product's profile menus (Enter/Esc); order letters fire without R2 through `NativeUnitCommands` (W placed a waypoint live), Tab holds the card, 1-4/Ctrl+1-4 recall/assign control groups and Space/Backspace jump to event/base (group and base verified live); inline font glyphs and configurable bindings missing (issue #8) |
| S030 | Hosted redistributable build and verification matrix | partial | `.github/workflows/verify.yml` covers Linux, Intel macOS, and Apple Silicon macOS; Windows not covered |
