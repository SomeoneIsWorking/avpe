# AVP:E save path

This document records the grounded save boundary for the supported
`SLUS-20147` executable. It is deliberately incomplete: the high-level profile
and game-save operations and their outer records are mapped, while the profile
payload fields and compressed world schema still require semantic decoding from
deliberately differing runtime saves. The BWJ wire decoder and the fixed
game-save prefix are now grounded; the object classes and editable field
meanings remain opaque.

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

The attached `CLoadSaveBuffer` stream starts with a two-byte BWJ mode word and
its first control word. Consequently the 0x20-byte level buffer begins four
bytes after the outer record, not immediately at `record + 0x118`. `SaveGame`
writes that level buffer through the compressor, then calls `GObject::SaveAll`.
`LoadGame` reads the same 0x20 bytes before loading the object stream.

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

## BWJ decode and fixed game-save prefix

The Ghidra decompilations of `CBWJCompressor` at `0x001088F0`,
`0x00108A10`, `0x00108AE0`, `0x00108C70`, `0x00108EE0`, and `0x00109170`
establish a little-endian 16-bit word stream. A mode word is followed by
16-token control words. A zero control bit copies one literal word; a set bit
reads a token whose high bits select a prior word distance and whose low bits
select a word length. A zero token is the explicit end marker. The observed
mode is `0x07FF`, which derives a five-bit length mask (`0x1F`) and a five-bit
distance shift. The implementation is in `src/avpe/save_format.py` and is
bounded by the caller before it allocates decoded output.

The same parser reads the fixed prefix described by `SaveAll` at
`0x0011D7C0`: the 0x20-byte level buffer, one game-time float, 0x2000 bytes
of handle bitmap words, the repeated game-time float, and then the object
stream at decoded offset `0x2028`. `LoadAll` at `0x0011D2A0` compares the two
time values before proceeding. The parser reports exact marker occurrences,
not an object count: `0x7FEA419D` marks each top-level object and the
top-level end record, while `0xBADF00DE` is shared by nested-object headers
and nested end markers. The `GObject::Save` decompilation at `0x0011DA30`
grounds each non-terminator record as a 16-byte header: marker, class ID, and
two opaque words. The parser distinguishes starts from zero-tailed end
records, counts class IDs, tracks maximum nesting depth, and rejects truncated
headers or an unbalanced object stack. It does not decode the subsequent
editable field records or assign gameplay meaning to class IDs.

### Finding (2026-08-29, object field serialization contract)

The same `GObject::Save` decompilation shows that an object body is not a
self-describing sequence of `(field id, length, value)` records. After the
16-byte object header and recursively serialized children, the saver walks the
class descriptor table at the object's type entry (`type + 0x1c`). Each
descriptor supplies a field offset, serialized size, and field kind. Kinds
`1`–`5` and `8` write the field bytes directly, using at least four bytes for
short fields. Kind `6` writes an eight-byte pointer-field description followed
by a four-byte referenced-object identity; kind `7` writes the same
description followed by a serialized pointer identity; kind `9` writes an
array description and one pointer identity per element, rejecting an array
whose identities do not resolve to the same saved-object index. The loader
uses the same descriptor table to consume these bodies and resolves class IDs
through `FindClassTypeEntry` before loading fields.

This grounds the missing parser dependency: class IDs alone are insufficient
to split or interpret editable fields. A native save writer must first extract
the supported class descriptor layouts and pointer-identity rules, then prove
them against deliberately differing real saves. Treating the opaque body as a
generic tagged record would accept bytes the game loader cannot consume.

### Finding (2026-08-29, live descriptor inventory and SaveEx boundary)

The live AVP:E class-type database at `0x003B10B0` has an array of 831 entries
(capacity 832). Its entries are 0x20 bytes; the class ID is at offset 0, the
name pointer at +4, the parent type pointer at +0x0c, and the editable
descriptor pointer at +0x1c. Each descriptor is 0x0c bytes: field ID, a
16-bit size, kind, flags, and object offset. The descriptor table terminates
when its first field-ID word is zero; the remaining eight sentinel bytes are
not required to be zero. `src/avpe/save_descriptor_probe.py` and
`tools/inspect_save_descriptors.py` implement bounded extraction and exact
descriptor-body splitting.

Against the class IDs found in both retained game saves, the live probe
resolved all 67 IDs and 6,304 descriptor fields. The observed kind totals were
319 kind-1, 2,275 kind-2, 1,709 kind-3, 72 kind-4, 99 kind-5, 59 kind-6,
1,475 kind-7, 233 kind-8, and 63 kind-9 fields. This is an inventory of the
loader's wire schema, not a gameplay interpretation of field IDs.

The descriptor-body splitter follows `GObject::Save`: scalar kinds use
`max(size, 4)` bytes; kinds 6 and 7 use an eight-byte field description plus
one four-byte identity; kind 9 uses the description plus one identity for each
four-byte array element. It validates pointer field IDs and sizes and returns
the consumed boundary while leaving any following virtual `SaveEx` payload
unconsumed.

`SaveAll` invokes each saved object's virtual `SaveEx` after `GObject::Save`.
The supported binary contains additional implementations at
`0x00110450` (`GFOWSaver`), `0x0019FFC0` (`GHiveNode`), `0x001A8850`
(`GAlienCarrier`), `0x001C0C80` (`GUnit`), `0x001DD8E0` (`GChestBurster`),
`0x001DF840` (`GDropShip`), `0x001F1DC0` (`GHugger`), `0x001F5E40`
(`GPlayerManager`), `0x00223090` (`GObjectAI`), `0x0023EF40` (`GDropPod`),
and `0x00248A30` (`GAlarm`); the base `GObject` implementation is at
`0x001070A0`. These payloads are not descriptor fields. The live parent-chain
probe selected `GObject` for 47 observed classes, `GUnit` for 9,
`GObjectAI` for 6, `GPlayerManager` for 3, `GDropShip` for 1, and `GFOWSaver`
for 1, with no missing class IDs. This maps the virtual dispatch boundary for
the observed records. The payload schemas remain separate: `GFOWSaver::SaveEx`
writes a bounded count followed by a sign-bit bitmap, while
`GPlayerManager::SaveEx` conditionally writes a fixed header plus four groups
of counted object/float triples. A whole-record parser must now decode those
selected payloads, including the variable-count `GObjectAI` message queue,
before it can claim complete record boundaries.

Running `tools/analyze_save_records.py` through the parser logic on the two
retained raw-card records produced these observations:

| Record | BWJ mode / shift / mask | Compressed bytes consumed | Decoded bytes | Level | Game time | Nonzero handle words | Marker occurrences (`7FEA` / `BADF`) |
|---|---:|---:|---:|---|---:|---:|---:|
| slot 0 | `0x07FF / 5 / 0x1F` | 160,544 | 640,724 | `M01/background.tbd` | 1466.283203125 | 31 | 190 / 2,335 |
| slot 1 | `0x07FF / 5 / 0x1F` | 160,584 | 640,836 | `M01/background.tbd` | 1482.699462890625 | 31 | 190 / 2,335 |

Both decoded time prefixes match their repeated time values byte-for-byte.
The level buffers contain the same NUL-terminated ASCII name and a retained
nonzero suffix byte (`01`) followed by padding; that suffix is not assigned a
meaning. The identical marker totals and changed game-time/decoded-size values
show that the decoder reaches the same broad serialization structure while
preserving state-dependent data. The object-header summary finds 189
top-level starts, 1,073 nested starts, 1,262 nested end records, maximum depth
3, and 67 distinct class IDs in each record; the class histogram is identical
between the two slots despite the body differences. This identifies structure,
not editable field meanings or gameplay semantics, and does not prove that the
original game loads either produced record.

## Evidence needed next

- Produce at least two isolated profile records whose settings differ and two
  isolated game saves whose progress differs. Two structurally distinct save
  bodies now exist; their decompressed object/class and gameplay meaning still
  needs to be identified.
- Decode editable field values with paired setting changes, including a case
  that must be rejected, to resolve unknown fields and checksums. Object-header
  structure, descriptor wire splitting, and malformed-input rejection are now
  covered by production parsers.
- Decode the selected `SaveEx` payloads for the 67 observed class IDs,
  including the variable-count `GObjectAI` message queue and conditional
  `GPlayerManager` state, before attempting a whole-record parser.
- Capture a normal in-game save completion and identify the narrow guest-call
  interception mechanism that can route the five `CProfile` operations to
  `AVPE::NativeSaves` while keeping the original game routines available as
  the differential oracle.

`tools/run_control_test.py --memory-card-source CARD.ps2` copies a formatted
card into the surfaceless/null-muted test profile, never opens the source for
writing, and emits `scratch/control-test/memory-card-proof.json` with source and
working hashes plus the changed-byte range. It is the runtime observation seam
for these comparisons; it is not the native backend.
