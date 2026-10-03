---
id: 8
title: Replace PS2 button prompts with PC-native prompts
status: open
symptom: The product still presents PlayStation 2 controller button prompts while keyboard and mouse are the shipping controls
state_items: S029
tags: input,ui,prompts,keyboard,mouse
created: 2026-08-27
updated: 2026-10-04
---

## Root cause

The prompts are rendered by AVP:E inside the guest frame, not by the PCSX2
frontend. PCSX2 presents the guest texture before its own optional OSD/UI
composition, and the standalone AVPE shell currently has no prompt overlay or
binding model.

## Prompt producer identified

The Select and Back prompt icons are `CRendPS2Mesh` resources drawn through
`CRendPS2Mesh::Render` (0x001884e0) and the workspace's
`CMeshWorkspace::GetMatrix` (0x001362c0) — the *same* implementation the
existing screen-bounds observer already hooks. Live capture in the Marine M1
pause menu, with the observer armed with the menu items' own image resources,
gives:

| prompt | resource | `CRendResource` vtable | render node | screen AABB |
|---|---|---|---|---|
| Select | 0x0135EB7C | 0x00334980 | 0x012E8AC0 | x 98..122, y 391..415 |
| Back | 0x0135EA3C | 0x00334980 | 0x012E95B0 | x 158..182, y 391..415 |

Both resolve through `resource->vtable[0x18]` = 0x001884e0 and
`workspace->vtable[0x14]` = 0x001362c0, drawn twice per capture.

## What was tried / dead ends

A Qt sibling overlay is not a sufficient replacement: the render surface is a
native child window, stacking is not portable, and additive text would leave
the PS2 glyphs visible. PCSX2's generic prompt font and ImGui OSD are unrelated
to the guest-rendered prompt and cannot replace it. A texture replacement or
masking pass would be unsafe until the guest resource identity and prompt
rectangles are grounded.

Falsified: the earlier hypothesis that the Select/Back meshes resolve to a
different `GetMatrix` vtable implementation than `CMeshWorkspace::GetMatrix`.
They resolve to exactly that implementation. `CRender::CoreRender` (0x001370f0)
dispatches the same `vtable[0x18]` slot but the title never reaches it; the live
draw passes through `CRender::Display` (0x00136fd0).

Falsified: the earlier hypothesis that the three failed correlations came from
needing a better filter or more capacity on the *mesh identity*. They came from
the opposite — the observer admitted every draw in the frame. One mission frame
issues 448 draw dispatches across far more resources than the bounded table
held, so the prompt icons were dropped before correlation. Arming the observer
with the two named resource addresses, and counting the rest as unadmitted,
makes a zero match count meaningful instead of a saturation artefact.

Also corrected: `GetScreenBoundingBox__13CRendBaseMesh` (0x00135af0) seeds
`[0]=[1]=+10000`, `[2]=[3]=-10000` and accumulates the transformed bounding-box
corners, so the four words read at `[sp+0x60]` are `minX, minY, maxX, maxY`. The
observer had labelled them `xmax, ymax, xmin, ymin`, which reported an inverted
rect.

## Remaining gap

The captured AABB is the mesh's *culling* box, not its placement. It is a 24x24
cell centred on the 16x16 glyph in x (glyph x 102..117 / 162..177 against cell
x 98..122 / 158..182) but sits about 18 px above it in y (glyph y 414..429 /
415..428 against cell y 391..415), so the guest-to-framebuffer vertical
transform is still ungrounded. The overlay cannot be placed from the AABB
alone; the draw geometry, or the renderer's vertical resolution and origin, has
to be established first.

The hard-coded host key mapping still needs replacing with a shared configurable
binding owner.

## Resolution

Not resolved. The prompt producer, its resource identity, and its culling box
are now grounded and observable; the placement rect and the PC-native overlay
itself remain open.