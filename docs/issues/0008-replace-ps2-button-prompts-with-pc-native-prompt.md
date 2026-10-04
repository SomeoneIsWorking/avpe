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

Inverting the grounded projection (screen = model + (110, 375)) puts both in the model's own
space, which is what the draw path works in:

```text
declared bbox   model y 16..40      (corners stored at mesh+0x1c/+0x28)
drawn sprite    model y 38..61      (screen y 413..436)
mesh position   model y 28          (mesh+0x10)
```

So the rasterised sprite occupies model y 38..61 while the declared bbox occupies 16..40: the same
24-unit extent, displaced 22 units, with the mesh origin at 28 between them. The horizontal extents
agree, so the discrepancy is purely in the model's Y axis and survives the projection unchanged.

Both the culling path and the draw path push the same workspace matrix
(`CMeshWorkspace::GetMatrix` fills it at `workspace+0x10`) and transform through the same window
(`0x003C6680`), so the difference cannot be in the matrix chain. It must be that the vertex
coordinates `PS2ProcessVerts` consumes are not in the same local frame as the stored bbox corners.

The owning `CRender` node is ruled out too. Dumping the node each prompt dispatch names gives the
resource at `node+0x1c` and the workspace at `node+0x20`, but no screen-placement fields: the
halfword `CRender::Display` compares at `node+0x30` is 7 for both prompts (a layer), `node+0x34`
that it passes to the vtable call is 0, and the remaining fields are parent pointers, flags
(`0x80008003` at +0x40) and a sequential id (794 and 793 at +0x48).

That leaves the vertex data itself as the only remaining carrier of the 22-unit offset.

The vertex input cannot be read at rest either. `CRendPS2Mesh::Render` takes the Material from the
owning `CRender` at `+0x28`, a `CVector4*` at `+0x18` and a `PS2SubMesh*` at `+0x38`, and passes
them to `PS2ProcessVerts` along with the mesh position at `mesh+0x10`. That owner is the node
`CMeshWorkspace::GetMatrix` returns from `workspace+4`, which turns out to be the same node
`CRender::Display` dispatches — the node holds the workspace at `+0x20` and the workspace holds the
node back at `+0x04`. Dumped between frames, all three of those pointers read as null, so they are
transient draw-time state rather than a resting description of the sprite. Catching them requires
observing during the draw, which means instrumenting `PS2ProcessVerts` entry rather than reading
guest memory from a probe.

## Correction: `PS2ProcessVerts` does no coordinate math, and the culling box is in pixels

Both halves of the reasoning above are wrong. A full decompilation and disassembly of
`PS2ProcessVerts` (0x00188720, 4228 bytes) shows it is a **DMA/GIF packet builder**, not a vertex
processor in the mathematical sense. It reads no vertex coordinates: it copies the 16-float model
matrix from `0x003C65E0` into the packet at `+0xA0` and hands VU1 a *pointer* to the guest's
vertex array via the in-FIFO at `0x6C000000 + n*0x20000`. The only floating-point literal in the
whole function is `1.0f`; there is no `mul`, no y-flip, no perspective divide. So the documented
next step — instrument its entry for the transient pointers and the "final screen coordinate" —
would have captured nothing. The real transform is in **VU1 microcode, which is not in this ELF**.

The model→screen transform the CPU *does* compute is `TransformPoint` at `0x00175BF0`, reached from
`GetScreenBoundingBox` (`0x00135af0`). It is fully recovered:

```text
p     = (vx, vy, vz, Wseed)                  Wseed = *(float*)0x003C5DD0  (a global, not 1.0)
M     = model(0x003C65E0) · screen(window)
c     = M · p                                row-vector v·M
invw  = (c.w == 0) ? 1e38f : 1/c.w           at 0x00175D38, applied in place
ScreenX = (c.x·invw)·(vw/2) + (x0 + vw/2)
ScreenY = (c.y·invw)·(vh/2) + (y0 + vh/2)
```

`screen(window)` is `CWindowData+0x140`, built by `CalcScreenMatrix` (`0x00176240`) as
`local · (CWindowData+0x0C0)`, where `local` scales by `vw/2`, `vh/2` and offsets by the viewport
centre. Those four constants come from `SetViewport` (`0x001754D0`) out of `layer[]·640` and
`layer[]·480` in `BeginLayer` (`0x00179220`). **There is no y-flip anywhere in the chain**, and
the result is top-origin with y increasing downward.

This also corrects the units. `GetScreenBoundingBox` does not report model space: it runs
`fptosi()` over the perspective-divided, viewport-scaled values, so `y 16..40` is **integer pixels,
top-origin**, for the current window. The 22-unit discrepancy is therefore **22 pixels**, not 22
model units, and the "invert the projection into model space" step above was operating on the wrong
quantity. Both numbers describe pixels: the culling rect from the observer, the sprite from a frame
capture.

Decisively: **the recovered formula contains no term that can produce a 22-pixel offset.** The only
additive term is the viewport centre, which both paths share, and the framebuffer 448-vs-480
discrepancy yields 32 or 16, not 22. Two carriers remain, and they cannot be separated statically:

1. `PS2ProcessVerts` ships a draw-path-only model translation, `puVar7[0x1C]/[0x1D]` =
   `(float)piVar9[0x15], (float)piVar9[0x16]`, read from the per-primitive parameter record.
   `GetScreenBoundingBox` never looks at that record, so this is the one translation the draw path
   sees and the culling path does not. A runtime read of `piVar9[0x16]` for the Select/Back
   submeshes would settle it.
2. VU1 microcode. `0x3C6690/94/98/9C`, written by `SetOutputScales` (`0x00189E10`), and
   `CWindowData+0x1E8..0x1F4` are **never read by any EE instruction** — they exist for VU1, and
   VU1 receives no viewport or projection from `PS2ProcessVerts`. Reading it needs a DMA dump of
   `0x11008000` or a hook on the IOP `sceDma` RPC targeting channel `vu1.code`.

One further correction: `GetResolution` (`0x00137B30`) returns 640 × **448** (`0x1C0`), not 640 ×
480. `PlatformInit` confirms `FRAMEBUFFER_Init(0x280, 0x1C0)`, while `BeginLayer` normalises the
layer rect against 480. That 448-vs-480 mismatch is real and worth chasing independently, though
it yields 16 or 32 rather than 22.

## Remaining gap

The declared bbox still cannot place an overlay: placing at it would sit 22 px above where the
guest drew the sprite and above the adjacent `Select`/`Back` label text. The offset is a
measurement, not a derivation, so shipping it as a placement constant would be a magic offset.

The mesh's draw record is not inline geometry. At `mesh+0x4c` it is a five-word structure whose
first word is the depth sort key and whose remaining words are guest pointers into submesh and
material descriptors. Scanning the whole reachable record region finds only three coordinate
values per prompt — the bbox corner `(12, 40, 5)` for Select and `(192, 40, 5)` for Back, with
`-53.335` and `1.0` — so the sprite's own corners are not stored there and placement cannot be
read from the mesh object. The vertex array is reached through `material+0x10`, and both prompt
addresses are runtime heap allocations with no static image.

Two placement routes are viable. Either the recovered transform is applied to the culling box once
the draw-path translation in (1) or the VU1 microcode in (2) is known, or the overlay locates the
glyph in the presented frame within a search window anchored on the culling box's column, which
the probe already demonstrates is reliable.

The hard-coded host key mapping still needs replacing with a shared configurable binding owner.

## Resolution

Not resolved. The prompt producer, its resource identity, and its culling box
are now grounded and observable; the placement rect and the PC-native overlay
itself remain open.