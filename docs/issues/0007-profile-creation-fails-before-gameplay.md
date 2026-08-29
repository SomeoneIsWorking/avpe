---
id: 7
title: Profile creation fails before gameplay
status: investigating
symptom: The windowed product reaches profile creation but cannot create a profile, preventing entry into gameplay
state_items: S013,S014,S016
tags: profile,save,memory-card,playability
created: 2026-08-27
updated: 2026-08-29
---

## Root cause

Not yet isolated. Profile creation is not one card write: the game creates the
profile directory and outer record, then provisions four padded save slots,
`List.ico`, `blart.dat`, and `icon.sys`. The product card contains the generated
`BASLUS-20147F991C326` directory string and `Extinction 1`, so the initial
creation path reached persistent storage and a later stage or subsequent menu
transition may be the failing operation.

## What was tried / dead ends

Static analysis mapped the complete high-level `CProfile` boundary and outer
record in [`../re/save-path.md`](../re/save-path.md). The isolated control runner
now accepts `--memory-card-source`, works only on a copied card, and reports
byte changes. No symptom-only patch has been applied to the legacy memory-card
path because G003 replaces that path with native saves.

### Finding (2026-08-29)

The available ignored source card contains one valid profile record and its
fixed 0x20-byte payload. The observed display name is `Extinction 1`, the
directory is `BASLUS-20147F991C326`, and the record fields are documented in
[`../re/save-path.md`](../re/save-path.md). This is a live payload/default
observation, not the deliberately differing pair required to resolve the
unknown fields; the card contains no grounded pair of differing game saves.

### Finding (2026-08-29, runtime owner)

A BIOS-backed pause-menu state exposed the live `CProfile` instance and its
`SetGameData` fields: object `0x003B2620`, payload `0x003D6A40`, size `0x20`,
revision `0x1CD9DEE3`, and four save targets. A direct diagnostic call to
`CProfile::SaveProfile` exceeded the 3,000,000-cycle shuttle budget and was
recovered by loading the known state. This is evidence that the save routine
must be exercised through its normal game path; it is not evidence that the
card write itself failed.

Targeted caller analysis identified the normal save path through
`GSavePacifyMenu::Process` (`0x00202F40`) and the overwrite/end-game variants
at `0x00202640` and `0x002092C0`. The save menu supplies the save name,
description, slot, and species to the `CShell` forwarder, so a direct four-
register diagnostic call cannot reproduce the `CProfile::SaveGame` ABI. The
remaining work is to decode the differing payloads, prove a load round-trip,
and identify the native interception boundary.

### Finding (2026-08-29, two normal game saves)

Two isolated BIOS-backed runs exercised the title's Save Game menu. The first
populated `BASLUS-20147F991C326/0.SAV`; a second run from that copied card
populated `BASLUS-20147F991C326/1.SAV` and returned to the pause/game flow
before clean shutdown. The two 0x7E400-byte save spans share the same outer
compatibility fields but their serialized bodies differ in 154,166 bytes.
This establishes a normal title-owned multi-slot write path and state-dependent
save content. It does not yet identify the decompressed object/class
differences, prove a load round-trip, or isolate the native interception point.

### Finding (2026-08-29, object fields are class-descriptor driven)

The `GObject::Save`/`Load` decompilation at `0x0011DA30`/`0x0011D570` closes
the apparent gap between the 16-byte object header and the opaque body. The
body is emitted by walking each class's descriptor table, not by writing a
self-describing field tag. Scalar kinds `1`–`5` and `8` write descriptor-sized
bytes (rounded to four for short values). Pointer kind `6` writes an 8-byte
field description and a 4-byte saved-object identity; kind `7` writes the
description and one pointer identity; kind `9` writes the description and one
identity per array element, requiring all identities to resolve consistently.
The loader consumes the same descriptor-defined sequence after resolving the
class ID through `FindClassTypeEntry`.

The next save-schema slice is class-specific payload decoding and
field-difference evidence. A generic record decoder or guessed field tags
would not preserve the game's loader contract and is explicitly out of scope.

### Finding (2026-08-29, live class descriptors and extra payloads)

The BIOS-backed paused state exposes the title's class-type database at
`0x003B10B0`: 831 live entries with capacity 832. The bounded descriptor probe
resolved every one of the 67 class IDs present in both retained game saves,
covering 6,304 descriptor fields. It also confirmed the descriptor sentinel is
the first zero field-ID word, even when the sentinel's trailing bytes are
nonzero. The reusable splitter now validates scalar widths and pointer-field
wire descriptions, extracts saved-object identities, and reports the exact
byte boundary before a class-specific `SaveEx` payload.

The remaining schema blocker is real: `SaveAll` invokes virtual `SaveEx` after
each object's descriptor body. The live parent chains now select `GObject` for
47 observed classes, `GUnit` for 9, `GObjectAI` for 6, `GPlayerManager` for 3,
`GDropShip` for 1, and `GFOWSaver` for 1. The binary also contains grounded
serializers for other classes (`GHiveNode`, `GAlienCarrier`, `GChestBurster`,
`GHugger`, `GDropPod`, and `GAlarm`) that were not selected by these 67 saves.
Their payloads are not descriptor fields: `GObjectAI` has a variable message
queue and `GPlayerManager` has conditional counted state. Bounded readers in
`src/avpe/save_ex.py` now cover the selected fixed, bitmap, message-queue, and
conditional group layouts. The AI reader now consumes the grounded message-type
table, including its dynamic-size fallback; the player-manager reader still
requires its active-state predicate. Integrate those readers with the recursive
object stream before claiming a whole-record reader or native writer.

### Finding (2026-08-29, message type table)

The live `MessageTypeDatabase` at `0x003B10C0` is a fixed 256-slot table whose
entries store creator address, size, and name pointer. The lookup uses only the
message type's low byte. The live probe found 92 registered slots and one
dynamic-size slot (`0x67`, `0xffffffff`); the latter follows `CMessage::GetSize`
by reading the message instance's 16-bit size at offset `+0x0c`. The pure
decoder now resolves fixed sizes, applies that dynamic fallback, and rejects
unregistered types by name rather than silently treating them as fixed records.

### Finding (2026-08-29, BWJ stream)

Ghidra decompilation of `CBWJCompressor` and `GObject::SaveAll` grounded the
save stream parser in `src/avpe/save_format.py`. Both retained records decode
with mode `0x07FF`, shift `5`, and length mask `0x1F`; the decoded fixed prefix
contains `M01/background.tbd`, matching repeated game-time values, an 8 KiB
handle bitmap, and the object stream at decoded offset `0x2028`. Slot 0 and
slot 1 decode to 640,724 and 640,836 bytes and each has 190 occurrences of
`0x7FEA419D` plus 2,335 occurrences of `0xBADF00DE`. These are marker
occurrences, not object counts: `0x7FEA419D` covers top-level objects and the
top-level end record, while `0xBADF00DE` is shared by nested headers and end
markers. The parser now recognizes the grounded 16-byte object headers and
rejects truncated headers or unbalanced marker structure without assigning
gameplay meaning. Both records contain 189 top-level objects, 1,073 nested
objects, 1,262 nested end records, one top-level end record, depth 3, and 67
distinct class IDs with identical histograms. The class IDs remain opaque, and
no editable-field semantics or load round-trip has been claimed.

## Resolution
