---
id: 8
title: Replace PS2 button prompts with PC-native prompts
status: open
symptom: The product still presents PlayStation 2 controller button prompts while keyboard and mouse are the shipping controls
state_items: S029
tags: input,ui,prompts,keyboard,mouse
created: 2026-08-27
updated: 2026-09-12
---

## Root cause

The prompts are rendered by AVP:E inside the guest frame, not by the PCSX2
frontend. PCSX2 presents the guest texture before its own optional OSD/UI
composition, and the standalone AVPE shell currently has no prompt overlay or
binding model. The exact AVP:E producer (font glyph, texture atlas, or prompt
sprite) and its draw rectangles have not yet been reverse-engineered.

## What was tried / dead ends

A Qt sibling overlay is not a sufficient replacement: the render surface is a
native child window, stacking is not portable, and additive text would leave
the PS2 glyphs visible. PCSX2's generic prompt font and ImGui OSD are unrelated
to the guest-rendered prompt and cannot replace it. A texture replacement or
masking pass would be unsafe until the guest resource identity and prompt
rectangles are grounded.

### Finding (2026-08-31, rendering ownership)

The generic menu path is not itself the prompt producer.
`GMenuItem::Display` at `0x00120AD0` only records visibility, dispatches the
item's render virtual at vtable offset `0xF4`, and displays children;
`GMenu::Display` likewise only performs input registration and delegates to
that base path. `CzFont::Render` at `0x001390E0` reads the concrete render
resource's NUL-terminated byte text, maps every byte through its font-local
glyph table, and submits sprite batches. Thus replacing generic menu labels or
adding a shell overlay cannot remove the PS2 glyphs. The next grounded anchor
is the concrete prompt item's `0xF4` render virtual and its text/resource
producer, from which its final sprite rectangles can be observed.

### Finding (2026-09-12, font render resource contract)

The supported ELF decompilation makes the font seam precise. `CzFont::Render`
reads the NUL-terminated text bytes from `CRender + 0x20 + 0x0C`; each byte is
looked up through the font's glyph table at `CzFont + 0x24`, and the glyph's
advance and height fields determine the submitted sprite position. Inline
control bytes adjust line position and horizontal alignment before one
`ProcessSprites` batch is emitted. This confirms that prompt replacement needs
the concrete render resource producer and its final rectangles; changing the
input resource name alone cannot establish which bytes reach this routine.

### Finding (2026-09-12, Press START archive producer)

The existing decoded-archive search found the exact `Press START button` bytes
29 times across all 5,558 structurally traversed TBF chunks (933 compressed),
so a raw string hit alone cannot select the live instance. One candidate is in
the MainMenu `LIST/PS2 ` group at archive offset `0x1EDA5C`. Its decoded
`DATX` at `0x1F02E8` has the string at offset `0xC10`; the group's `PUBL`
and `EXTA` tables name that export
`_autostring_2CC0FD68_25BA17B3_008_`. They name the object at decoded offset
`0xBB0` `PressStart_StartButton`. `GMenuItem::SpecifyEditable` at `0x0011F190`
registers `pText` as the string field at object offset `+0x148`. The title's
field-name CRC (`zlib.crc32(name) ^ 0xFFFFFFFF`) for `pText` is `0x7AF23FC8`,
exactly the `DATX` field tag at `0xBDC`; its pointer value at `0xBE4` is
`0xC10`. The `OFFS` table lists that pointer location.

A real AVP:E run restored at the title screen supplied the live discriminator:
`GET /input/menu` identified `GPressStartMenu` (`0x00342A50`), its focused
`GMenuButton` (`0x00331610`), and the focused item's `pText` address
`0x0154BBD0`. `GET /mem/read?addr=0x0154BBD0&len=0x30` returned the
NUL-terminated bytes `Press START button`. The standalone title screen also
visibly renders the same text. A second live read followed the focused item
at `0x01346830`: its embedded text `CRender` starts at `+0x1D0`, and that
renderer's resource pointer at `+0x20` is `0x01346A90`. The resource contains
`Press START button` directly at `+0x0C`, the exact byte location read by
`CzFont::Render`. This matches `GMenuItem::ReformatText` (`0x00120250`),
which feeds the embedded renderer through `CRender::AttachText`
(`0x001371E0`). These observations ground the authored field and live
title-menu font-resource path; they do not establish which of the 29 archive
copies was loaded or the final sprite rectangles. The X/Triangle glyphs
need their own producer and rectangle evidence. Static vtable inspection
rules out `+0xF4` alone as that discriminator: both `GPressStartMenu`
(`0x00342A50`) and `GMenuButton` (`0x00331610`) resolve that slot to the
generic `GMenuItem::Redraw` at
`0x00120890`. That routine composes the `CRender` resource and consults
its `+0x58` virtual, but the static vtable alone cannot identify the live
text or glyph producer.

### Finding (2026-08-31, controller-resource selection)

`GInputDevice::LoadGamepadTbd` at `0x00114250` chooses a controller name and
loads the title resource formatted as `Gamepad%s.tbd`. The static table includes
`DualShockPS2`, `ThrustMaster`, `HammerHead`, `HammerHeadUSB`, and
`DualShockPC`; the corresponding named input actions include each shoulder and
cluster-button press. This is the control-mapping resource seam, not prompt
rendering evidence: neither the loader nor the prompt-menu vtable establishes
which text/glyph resource reaches `CzFont::Render`, so changing a `.tbd` would
not yet be a justified prompt replacement.

## Resolution

Not resolved. The correct implementation seam is a dedicated final-frame GPU
prompt overlay fed by an atomic CPU-produced prompt context, but it remains
blocked on identifying the guest prompt resource/rectangles and on replacing
the hard-coded host key mapping with a shared configurable binding owner.
