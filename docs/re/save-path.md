# AVP:E save path

This document records the grounded save boundary for the supported
`SLUS-20147` executable. It is deliberately incomplete: the high-level profile
and game-save operations and their outer records are mapped, while the profile
payload fields and compressed world schema still require semantic decoding from
deliberately differing runtime saves.

## High-level owner

`CProfile` at singleton slot `0x0036703C` owns profile/card selection and all
normal save operations. Its direct boundary is compact and title-specific:

| Address | Function | Contract observed statically |
|---|---|---|
| `0x0012FAA0` | `CProfile::LoadProfile(int)` | Read the selected profile's 0x118-byte record, validate revision and payload size, then read the profile payload. |
| `0x0012FCE0` | `CProfile::SaveProfile()` | Write the 0x118-byte record followed by the fixed-size profile payload. |
| `0x0012FF90` | `CProfile::CreateProfile(char const*)` | Create the profile definition and directory, save the profile record, then provision the auxiliary files. |
| `0x0012F940` | `CProfile::SetGameData(void*, int, uint, uint)` | Store the profile-payload pointer, payload size, game-data revision, and save-slot count in the `CProfile` instance. |
| `0x00130000` | `CProfile::LoadGame(int)` | Read a save record, attach the decompressor, load the level named in the next 0x20 bytes, then deserialize all game objects. |
| `0x00130170` | `CProfile::SaveGame(...)` | Save the profile, write a save record and 0x20-byte level name, compress all game objects, pad the slot, then rewrite the finalized record. |
| `0x001304A0` | `CProfile::BuildProfileList()` | Enumerate `BASLUS-20147*` directories and validate their outer records. |
| `0x00130800` | `CProfile::BuildGameList()` | Enumerate the current profile's numbered saves and reject mismatched profile ID, revision, or payload size as damaged. |

`CShell::SaveGame` at `0x0016FAE0` and `CShell::LoadGame` at `0x0016FB00`
are thin forwarders to this owner. A native save bridge therefore belongs at
the `CProfile` boundary; replacing generic `CZFile` would also capture unrelated
disc and host file traffic and would not express the profile invariants.

All of these routines use zero for success and nonzero for failure.

## Card namespace and provisioning

`CProfileDef::CreateProfile` at `0x0012F4A0` computes the CRC32 of the visible
profile name and creates `BASLUS-20147%08X`. `CProfileDef::PostCreate` at
`0x0012F5B0` then provisions:

- four numbered `%s/%d.SAV` files by default, each padded to `0x7E400` bytes;
- `List.ico` from the embedded `PS2SysIcon` data;
- `blart.dat`, padded to `0xC00` bytes;
- `icon.sys`, populated with the product/profile display strings.

The profile record itself is stored at `%s/%s`: the directory name repeated as
the filename. `CZFile` flags `0x1001` and `0x1002` select memory-card read and
write respectively; its PS2 platform layer maps those operations to `sceMc*`
calls and synchronous completion.

Profile creation is consequently a multi-stage transaction. The observed
product card already contains the generated `BASLUS-20147F991C326` string and
`Extinction 1`, proving that at least part of creation reached persistent card
storage. That observation does not identify which later write failed.

## Outer record

Both profiles and numbered game saves begin with a `CProfileDef` record of
`0x118` bytes:

| Record offset | Size | Grounded meaning |
|---|---:|---|
| `0x000` | `0x80` | Display/profile or save name, NUL-terminated. |
| `0x080` | `0x80` | Directory or numbered save path, NUL-terminated. |
| `0x100` | 4 | Profile-name CRC32 in a profile; owning profile CRC32 in a game save. |
| `0x104` | 4 | Unknown; must be resolved from differing records. |
| `0x108` | 4 | Game-data revision used to reject incompatible records. |
| `0x10C` | 4 | Profile modification time in a profile; initialized to `-1` before a record is populated. Its game-save meaning remains unproven. |
| `0x110` | 4 | Fixed profile/game-data payload size used for compatibility checks. |
| `0x114` | 4 | Stable profile ID derived from name CRC plus creation time. Its game-save meaning remains unproven. |

The profile payload immediately follows this record and has the size supplied
through `CProfile::SetGameData` (`CProfile + 0x18` pointer, `+0x1C` size,
`+0x20` revision). A game save instead writes a 0x20-byte level identifier and
then a BWJ-compressed `GObject::SaveAll` stream through `CLoadSaveBuffer`.

## Single observed profile record

The ignored user-supplied card `scratch/control-test/source-card.ps2` contains
one profile record for `BASLUS-20147F991C326`. Its 0x118-byte record followed by
the 0x20-byte payload was extracted from the card file entry and has record
SHA-256 `7b53c401b617cfbabe5729f3584303c6fd72b48f19ad47bdf33d48e99a89eb4f`.
The card SHA-256 is
`55237edfb8bd977e22ecf84ae2d1a942f8167fd3cbf9798376259342120f2b2b`.

| Offset | Observed value |
|---:|---|
| `0x000` | `Extinction 1` |
| `0x080` | `BASLUS-20147F991C326` |
| `0x100` | `0xF991C326` |
| `0x104` | `0x00000000` |
| `0x108` | `0x1CD9DEE3` |
| `0x10C` | `0x40AAF870` |
| `0x110` | `0x00000020` |
| `0x114` | `0x3A3894EE` |

The payload bytes are
`11 10 10 00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 00 00 80 3F 00 00 80 3F 00 00 80 3F`.
This grounds one live profile payload and confirms the record's profile-name
CRC and fixed payload size. It does not resolve the unknown field at `0x104`,
the timestamp/ID semantics, or any game-save payload.

## Live `CProfile` data contract

A BIOS-backed pause-menu state provided a second, independent observation of
the in-memory owner. The singleton slot `0x0036703C` contained the
`CProfile*` value `0x003B2620`. Its `+0x18` data pointer was `0x003D6A40`,
`+0x1C` was `0x20`, `+0x20` was `0x1CD9DEE3`, and `+0x24` was `4`. Reading
`0x003D6A40..0x003D6A5F` produced the same 0x20-byte payload recorded above.
This confirms the runtime `SetGameData` contract and that the fixed payload is
game-owned memory, not a card-only reconstruction.

The diagnostic EE-call shuttle is not a valid save trigger: calling
`CProfile::SaveProfile` directly from the pause-menu state exceeded its
3,000,000-cycle budget and required a state reload. The routine synchronously
drives the title's memory-card service and must be observed through the normal
game save path before its completion boundary can be used by a native bridge.

## Normal game save callers

The analyzed callers identify the title-owned path that must be exercised for
runtime evidence. `GSavePacifyMenu::Process` at `0x00202F40` sets the active
profile target, optionally creates the profile, and calls the `CShell` forwarder
with a save name at menu-object offset `0x2C0`, a description at offset
`0x1B0`, slot `0`, and the current species. `CShell::SaveGame` at
`0x0016FAE0` forwards those arguments to `CProfile::SaveGame`; on success the
menu waits three seconds using the title's game timer before returning to its
parent menu. `GOverwritePacifyMenu::Process` at `0x00202640` follows the same
save call after removing existing slots, while
`GEndGameSaveProfileMenu::Process` at `0x002092C0` saves the profile after its
profile-name and identity checks.

This gives the native bridge a narrow high-level seam: preserve the
`CProfile` operation's arguments and zero/nonzero result, while keeping the
menu-owned success/error transitions and the original routines available for
differential comparison. The `/ee/call` diagnostic endpoint cannot faithfully
invoke the five-argument `CProfile::SaveGame` ABI because it only stages
`a0..a3`; normal menu execution is therefore required for game-save captures.

## Two normal game-save records

The BIOS-backed control runner exercised the actual Save Game menu on isolated
copies of the supplied card. The first run returned to the pause menu after
writing slot 0. Its card copy has SHA-256
`36503b39dcfbdcb3ff5ad1c0d6b0f3b305ec93cf6b487d8e08e01e9eb2ff9d38`; the
slot-0 record at logical offset `0xB800` has record SHA-256
`ca867e3add58a2307ac63fb7cd34b1cca52d838c26117b89c1612d6a6f4c37bf`, display
text `Extinction 1`, `Marine 1`, and `2026/08/26 8:36:09`, and path
`BASLUS-20147F991C326/0.SAV`. Its fields are
`[0xF991C326, 0, 0x1CD9DEE3, 0xFFFFFFFF, 0x20, 0]`, matching the grounded
profile identity and payload-size checks.

The second run started from that copy, selected a distinct empty slot through
the same Save Game menu, and returned to the pause/game flow before clean
shutdown. Its final card has SHA-256
`438d481548b465b1507aef0187ffbb0f09aaebd71ed7b6739b44b842048c2bf6`. The
slot-1 record at logical offset `0x8A000` has record SHA-256
`b3eb60e3de3449ea76578332bf96b311ad68da56588f7696ab26090110d16d6d`, display
text `Extinction 1`, `Marine 1`, and `2026/08/26 8:35:59`, and path
`BASLUS-20147F991C326/1.SAV`. It has the same six identity/compatibility
fields as slot 0. The slot-0 and slot-1 serialized bodies are not identical:
after the common outer record and level-name prefix, 154,166 bytes differ;
their body hashes are respectively
`d1a5ab95a99c458c387765f3a14cf53804c8b4aaa2a68f3d3bcf0b953d34d3e5` and
`0ca22a19027d73b3c32aa17347a219e27210e79476bb50f3f450c5923d391235`.

This proves that the normal title-owned path can persist two separate,
structurally valid numbered save records and that the compressed payload is
state-dependent. It does not yet identify the decompressed object differences,
prove a load of either record, or provide the native-save interception.

## Evidence needed next

- Produce at least two isolated profile records whose settings differ and two
  isolated game saves whose progress differs. Two structurally distinct save
  bodies now exist; their decompressed gameplay meaning still needs to be
  identified.
- Compare the records and decompressed streams, including a case that must be
  rejected, to resolve unknown fields and checksums.
- Capture a normal in-game save completion and identify the narrow guest-call
  interception mechanism that can route the five `CProfile` operations to
  `AVPE::NativeSaves` while keeping the original game routines available as
  the differential oracle.

`tools/run_control_test.py --memory-card-source CARD.ps2` copies a formatted
card into the surfaceless/null-muted test profile, never opens the source for
writing, and emits `scratch/control-test/memory-card-proof.json` with source and
working hashes plus the changed-byte range. It is the runtime observation seam
for these comparisons; it is not the native backend.
