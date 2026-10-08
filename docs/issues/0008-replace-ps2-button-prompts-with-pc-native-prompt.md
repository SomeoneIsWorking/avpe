---
id: 8
title: Replace PS2 button prompts with PC-native prompts
status: open
symptom: The product still presents PlayStation 2 controller button prompts while keyboard and mouse are the shipping controls
state_items: S029
tags: input,ui,prompts,keyboard,mouse
created: 2026-08-27
updated: 2026-10-08
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

## Screen space

The framebuffer is 640 x 448: `CRendAPI::GetResolution` (`0x00178930`) returns the RECT
`{0, 0, 640, 448}` at `0x003C9FE0`, `FRAMEBUFFER_Init(0x280, 0x1C0)` has one caller, and
`sceGsSetDefDrawEnv` centres it with `XYOFFSET` `OFX = 1728`, `OFY = 1824` (`2048 - 224`). The draw
area, pointer clamp, menu pointer centre `(320, 224)` and screen-bbox culling all use 448.

Window viewports are a separate box. `BeginLayer` (`0x00179220`) scales layer rects by 640 x 480, and
live, seven of nine windows are 640 x 480; the prompts draw in window 7 (`*0x003C6680`), 640 x 480,
so `vh/2 = cy = 240`. Rows 448..480 of such a window have no pixels under them.

`/snap` (`NativeSnapshotRoute`) calls `SaveMemorySnapshot(0, 0, apply_aspect=true, ...)`, so its
640 x 480 image is the 448-row framebuffer stretched by 480/448. Snapshot rows must be scaled by
448/480 before they are compared with guest coordinates.

## Culling transform (CPU)

`GetScreenBoundingBox` (`0x00135AF0`) projects the stored bbox corners at `mesh+0x1C..0x30` through
`TransformPoint` (`0x00175BF0`):

```text
c       = (x, y, z, Wseed) * (Model(0x003C65E0) * Screen(CWindowData+0x140))
ScreenY = (c.y / c.w) * (vh/2) + (y0 + vh/2)       top-origin, framebuffer pixels
```

`Screen` is built by `CalcScreenMatrix` (`0x00176240`) from `CWindowData+0xC0` and the viewport.
For the prompts this gives x 98..122 / 158..182, y 391..415.

## Draw transform (VU1)

`PS2ProcessVerts` (`0x00188720`) builds the per-mesh VU1 packet; it does no coordinate math. The
geometry it ships is the submesh vertex stream, decoded by `src/avpe/ps2_submesh_stream.py`:

```text
mesh+0x4C -> submesh record; record+0x10 -> stream pointer array -> stream
+0x00  u16 count, u16 count, u16 packet offset (from +4), u16 0
+0x08  f32 scale x, y, z          (the bbox max corner)
+4+off DMAtag RET qwc=4 | VIF NOP | UNPACK V4-16 num=8 addr=0x25 FLG
       per vertex: (x, y, z, u) (nx, ny, nz, v) int16
```

Live, both prompts decode to exactly the stored bbox (y 16..40, z 5, normal `(0, 0, 1)`).
Packet words w28/w29 (`piVar9[0x15]`/`[0x16]`, measured 0.0) are UV offsets added at micro
`0x202..0x203`, not a position translation.

The VU1 program is in the ELF inside `SpriteMeshDMA` (`0x002CEB00`, 675 QWC), sent every frame by
`EndFrame` over VIF1. The packet is `STCYCL 1,1`, `UNPACK V4-32 num=64 addr=0` (data memory
q0..q63 = guest `0x2CEB10 + 16q`), `DIRECT 2`, `BASE 0x58`, `OFFSET 0x100`, then six `MPG`
(cmd `0x4A`) loading micro `0x000..0x4FF` and `0x7F0`, then `MSCAL 0`. Code starts at guest
`0x2CEF50`; `_$code_mesh` is micro `0x06F`, `_$comp_verts` `0x180`. Read the ELF little-endian.

Per vertex, from the instructions:

```text
pos    = ITOF15(q16) * q31.xyz                       stream scale; no additive term
clip   = (pos, 1) * (Model q33..36 * VP slot+0..3)   composed at micro 0x09A..0x0A9
screen = clip.xyz / clip.w * slot+4.xyz + slot+5.xyz  micro 0x216..0x217, FTOI4 at 0x221
```

The slot is `ViewportData` (`0x002CEBD0 + 0x60 * window`, VU1 q12 + 6 * window), written by
`EndFrame` from `CWindowData` (`0x003C66A0 + 0x210 * window`):

```text
slot+4 = (halfW WD+0x1D4, halfH WD+0x1DC, ...)
slot+5 = (cx WD+0x1D0 + 1728, cy WD+0x1D8 + 1824 - 8.0, ...)    EndFrame 0x00178DB4..0x00178E88
```

After the GS subtracts `XYOFFSET`, `y_px = n_y * halfH + cy - 8`. `CalcScreenMatrix` applies the same
`halfH` and `cy` and nothing else, so **VU1 draws every mesh 8 framebuffer pixels above where the
culling transform puts it; horizontal is identical.** The `8.0` is the literal `0x41000000` loaded
at `0x00178DCC`.

## Measurement

The mesh-bounds probe reports the drawn sprite in framebuffer space
(`drawn_ymin_framebuffer`). In the Marine M1 pause menu both prompts measure a top edge at row
385.5 against a culling top of 391; the luminance threshold fires inside the disc's dark rim, which
spans framebuffer rows ~383..407, the VU1 prediction of 391..415 minus 8. The earlier "22 px below"
figure compared stretched snapshot rows (413) with framebuffer rows (391).

## Placement

A prompt's on-screen rect is its culling rect moved up by the `EndFrame` constant:

```text
framebuffer rect = GetScreenBoundingBox(mesh) - (0, 8)    in the 640 x 448 framebuffer
```

The overlay maps that rect from the 640 x 448 framebuffer into the presented display rect.

## Dead ends

- A Qt sibling overlay: the render surface is a native child window and stacking is not portable;
  additive text would leave the PS2 glyphs visible. PCSX2's prompt font and ImGui OSD are unrelated.
- A different `GetMatrix` implementation for the prompts: they use `CMeshWorkspace::GetMatrix`.
- Unarmed correlation: one mission frame issues 448 dispatches; the observer must be armed with the
  two resource addresses.
- A 22 px offset carrier (draw-path translation, vertex data, GS registers, 448-vs-480 viewport
  scale): all measured or decoded as absent; the 22 px was snapshot stretch plus the VU1 `-8`.

## Remaining gap

- The host overlay itself: an owner that reads the two prompt rects through the culling observer,
  applies the VU1 offset above, and draws PC-native prompts over them.
- The hard-coded host key mapping still needs replacing with a shared configurable binding owner.

## Resolution

Not resolved. The producer, its resource identity, and its on-screen rect are grounded; the
PC-native overlay remains open.
