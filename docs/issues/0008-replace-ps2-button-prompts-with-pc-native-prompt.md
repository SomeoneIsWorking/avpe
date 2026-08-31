---
id: 8
title: Replace PS2 button prompts with PC-native prompts
status: open
symptom: The product still presents PlayStation 2 controller button prompts while keyboard and mouse are the shipping controls
state_items: S029
tags: input,ui,prompts,keyboard,mouse
created: 2026-08-27
updated: 2026-08-28
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

## Resolution

Not resolved. The correct implementation seam is a dedicated final-frame GPU
prompt overlay fed by an atomic CPU-produced prompt context, but it remains
blocked on identifying the guest prompt resource/rectangles and on replacing
the hard-coded host key mapping with a shared configurable binding owner.
