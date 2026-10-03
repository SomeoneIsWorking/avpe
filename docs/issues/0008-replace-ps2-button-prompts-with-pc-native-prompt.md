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
`workspace->vtable[0x14]` = 0x001362c0.

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

## Renderer vertical transform is grounded

`GetResolution__9CRendererFv` (0x00137b30) returns the array `{0, 0, 640, 480}`, so the
culling rect and the 640x480 framebuffer are the same space and the vertical gap is neither a
flip nor a scale. `GetCurrentWindow__Fv` (0x00175290) returns the single global
`0x003C6680`, which is the same window `CRendPS2Mesh::Render` and
`GetScreenBoundingBox__13CRendBaseMesh` both transform through.

Reading the live `CRendPS2Mesh` (0x50 bytes, built by `TbdConstruct_CRendPS2Mesh` at
0x00188420) gives position at +0x10 = `(0, 28, 5)`, the two bounding corners
`GetScreenBoundingBox` reads at +0x1c/+0x20/+0x24 = `(12, 40, 5)` and
+0x28/+0x2c/+0x30 = `(-12, 16, 5)`, a radius at +0x34 of `16.97` (= 24/sqrt(2)), the record
count at +0x48, and the record array at +0x4c. The declared bbox is therefore a 24x24 cell in
model space, and projecting it reproduces the captured rect exactly:

```text
model  x -12..12   y 16..40        screen x  98..122   y 391..415
scale  1.000000    1.000000        offset (110, 375)
```

All four corners land inside the captured rect, so the captured rect is the declared bbox under
a 1:1 axis-aligned projection. There is no vertical flip.

The declared bbox still does not bound what is rasterised. The probe now measures the drawn
sprite in the same frame it captures the rect, by luminance (the button is a light grey disc, the
mission HUD behind it is dark water). With the pause menu held open:

```text
select  culling x  98..122  y 391..415   sprite y 413..436 (24 rows)  offset +22
back    culling x 158..182  y 391..415   sprite y 413..436 (24 rows)  offset +22
```

The label text occupies y 437..449, below the sprite. The sprite is exactly as tall as the culling
cell and sits a constant 22 px below it; its horizontal centre matches the culling box's to within
half a pixel in both cases, so the two describe the same object with a vertical-only discrepancy.

Forty rects across 4480 observed draws produce exactly one distinct rect per prompt, so the menu
is not animating and the offset is a stable property of how this mesh is drawn, not a capture
artefact.

## Remaining gap

The declared bbox cannot place an overlay: placing at it would sit 22 px above where the guest
drew the sprite and above the adjacent `Select`/`Back` label text. The offset above is a
measurement, not a derivation, so shipping it as a placement constant would be a magic offset; the
transform that produces it still has to be found.

The mesh's draw record is not inline geometry. At `mesh+0x4c` it is a five-word structure whose
first word is the depth sort key and whose remaining words are guest pointers into submesh and
material descriptors. Scanning the whole reachable record region finds only three coordinate
values per prompt — the bbox corner `(12, 40, 5)` for Select and `(192, 40, 5)` for Back, with
`-53.335` and `1.0` — so the sprite's own corners are not stored there and placement cannot be
read from the mesh object. The vertex array `PS2ProcessVerts` (0x00188720) consumes is reached
through `material+0x10`. `PS2ProcessVerts` is a 4228-byte light-tree vertex processor that submits
through `ClaimDMABuffer` (0x0017ad70), so the next step is to instrument where it writes the final
screen coordinate for these quads rather than reading it statically.

Two placement routes are viable once that is grounded. Either the derived transform is applied to
the culling box, or the overlay locates the glyph in the presented frame within a search window
anchored on the culling box's column, which the probe already demonstrates is reliable. Both need
the same missing derivation.

The hard-coded host key mapping still needs replacing with a shared configurable binding owner.

## Resolution

Not resolved. The prompt producer, its resource identity, and its culling box
are now grounded and observable; the placement rect and the PC-native overlay
itself remain open.