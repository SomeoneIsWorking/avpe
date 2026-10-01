---
id: 8
title: Replace PS2 button prompts with PC-native prompts
status: open
symptom: The product still presents PlayStation 2 controller button prompts while keyboard and mouse are the shipping controls
state_items: S029
tags: input,ui,prompts,keyboard,mouse
created: 2026-08-27
updated: 2026-09-18
---

## Root cause

The prompts are rendered by AVP:E inside the guest frame, not by the PCSX2
frontend. PCSX2 presents the guest texture before its own optional OSD/UI
composition, and the standalone AVPE shell currently has no prompt overlay or
binding model. The profile menu's X icon is now traced to its `Select` item's
`CRendPS2Mesh`, while other prompt producers and their draw rectangles remain
to be identified.

## What was tried / dead ends

A Qt sibling overlay is not a sufficient replacement: the render surface is a
native child window, stacking is not portable, and additive text would leave
the PS2 glyphs visible. PCSX2's generic prompt font and ImGui OSD are unrelated
to the guest-rendered prompt and cannot replace it. A texture replacement or
masking pass would be unsafe until the guest resource identity and prompt
rectangles are grounded.

## Resolution

Not resolved. The correct implementation seam is a dedicated final-frame GPU
prompt overlay fed by an atomic CPU-produced prompt context. Live capture of
the candidate screen-bounds call works end-to-end and produces real rect
data, but three independent correlation attempts — two by size/position, one
by the live Select/Back mesh addresses themselves — have not matched a
captured sample to either icon. The likeliest explanation is now that the
Select/Back meshes render through a different `GetMatrix` vtable
implementation than the hooked `CMeshWorkspace::GetMatrix`, not that the
current hook needs a better filter or more capacity. The exact prompt-icon
identification and its guest-to-screen coordinate transform are still open,
and the hard-coded host key mapping still needs replacing with a shared
configurable binding owner. The next step is hooking
`Render__12CRendPS2Mesh`'s own vtable read to identify which `GetMatrix`
implementation the Select/Back meshes actually resolve to.
