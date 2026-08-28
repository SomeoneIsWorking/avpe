---
id: C016
kind: claim
status: holds
created: 2026-08-27
tags: save,profile,re
depends: docs/re/save-path.md
reconfirmed: 2026-08-29
verified_at: 2026-08-29 00:01:59
---

## Claim

AVP:E's normal profile and game-save boundary is CProfile, with a 0x118-byte outer record, multi-file profile provisioning, fixed profile payload, and BWJ-compressed game-object saves

## Evidence

SLUS-20147 symbol inventory and targeted Ghidra decompilation identify CProfile functions 0x0012FAA0-0x00130800, CProfileDef creation at 0x0012F4A0-0x0012F7F0, CZFile memory-card flags, literal BASLUS-20147%08X and numbered .SAV paths, exact 0x118 record reads/writes, 0x20 level-name write, CLoadSaveBuffer compression, and 0x7E400 slot padding; docs/re/save-path.md records the field-level derivation

## What would falsify it

a runtime trace shows normal profile or game saves bypassing CProfile, a deliberately differing valid record contradicts the recorded outer layout, or a save produced through these functions cannot be loaded by the original game

## Re-confirmed 2026-08-29

After a6c1103, the ignored user-supplied source card still contains one profile file record with a 0x118-byte outer record plus a 0x20-byte payload: display Extinction 1, directory BASLUS-20147F991C326, CRC 0xF991C326, revision 0x1CD9DEE3, fixed payload-size field 0x20, and record SHA-256 7b53c401b617cfbabe5729f3584303c6fd72b48f19ad47bdf33d48e99a89eb4f. A BIOS-backed paused state independently exposed `CProfile* = 0x003B2620`, payload pointer `0x003D6A40`, payload size `0x20`, revision `0x1CD9DEE3`, and four save targets, with payload bytes matching the card record. Targeted caller analysis additionally identified `GSavePacifyMenu::Process` (`0x00202F40`), `GOverwritePacifyMenu::Process` (`0x00202640`), and `GEndGameSaveProfileMenu::Process` (`0x002092C0`) as normal profile/save callers. This confirms the live `CProfile` data contract and narrows the interception seam; it does not claim differing profile/game-save coverage or a captured save completion.

## Re-confirmed 2026-08-29 — two normal game saves

Two BIOS-backed Save Game menu runs on isolated copies of the supplied card
persisted separate numbered records. Slot 0 at `0xB800` has record SHA-256
`ca867e3add58a2307ac63fb7cd34b1cca52d838c26117b89c1612d6a6f4c37bf` and
path `BASLUS-20147F991C326/0.SAV`; slot 1 at `0x8A000` has record SHA-256
`b3eb60e3de3449ea76578332bf96b311ad68da56588f7696ab26090110d16d6d` and
path `BASLUS-20147F991C326/1.SAV`. Both carry the same profile CRC,
revision, payload size, and save-record compatibility fields. Their common
record/level prefix is followed by 154,166 differing serialized body bytes.
The first card copy hashes to
`36503b39dcfbdcb3ff5ad1c0d6b0f3b305ec93cf6b487d8e08e01e9eb2ff9d38`; the
final two-slot copy hashes to
`438d481548b465b1507aef0187ffbb0f09aaebd71ed7b6739b44b842048c2bf6`.
This re-confirms the title-owned normal save path and state-dependent body,
but does not claim decompressed gameplay semantics, load round-trip, or native
save interception.

## Re-confirmed 2026-08-29 — BWJ wire structure

Ghidra decompilation of `CBWJCompressor` and `GObject::SaveAll` now has a
tracked Python parser/test seam for the evidence. It decodes both retained
records with mode
`0x07FF`, shift `5`, and length mask `0x1F`; both expose the expected level
prefix, equal repeated game-time values, 8 KiB handle bitmap, and object-stream
offset `0x2028`. Slot 0 and slot 1 decode to 640,724 and 640,836 bytes with
identical marker totals (190 `0x7FEA419D` occurrences and 2,335
`0xBADF00DE` occurrences). This grounds the wire structure only; class IDs,
field semantics, produced-save load, and native interception remain open.
