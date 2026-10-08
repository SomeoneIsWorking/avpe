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

A prompt's on-screen rect is its culling rect moved by the VU1 draw-env offset:

```text
offset = ViewportData slot origin - window centre - (2048 - framebuffer / 2)
       = (0, -8) for every window EndFrame writes
```

`NativePromptPlacement` reads the slot origin (`0x002CEBD0 + 0x60 * window + 0x50`) and the window
centre (`WD+0x1D0`/`+0x1D8`) at EndFrame's VIF1 kick (`0x001791AC`), so the 8 is the guest's own
value. Live in the Marine M1 pause menu, `/prompt/placement` reports Select at 98..122 x 383..407
and Back at 158..182 x 383..407.

## Glyph identity

Every menu button icon is one of five `CRendPS2Mesh` publics in `MASTER.TBD`, all on
`__avp_art_menus_main_ps2buttons_tga` except R1:

| label | GetCRC | button |
|---|---|---|
| `TopButton` | `0x5F8391BF` | Triangle |
| `BottomButton` | `0xA67152A0` | Cross |
| `RightButton` | `0x361BAEBF` | Circle |
| `LeftButton` | `0x0CCCE1E0` | Square |
| `R1Button` | `0x0FA27263` | R1 |

Each is found through the TBD fixup symbol table (`pSymbolTable__16CTbdFixupManager` at
`0x00367350` -> `{mask, buckets}`; bucket `buckets + (key & mask) * 0xC` = `{entries, last index,
cap}`; entry `{value, key, label}`; `CHashTableElement::Find` at `0x001731A0` scans `0..last`
inclusive). Live, `BottomButton` and `TopButton` resolve to the Select/Back meshes `0x0135EB7C` and
`0x0135EA3C`. The pause items are `MainSelectButton` (`0x6449F1DE`) and `MainBackButton`
(`0x36D11C7B`), whose authored `pResource` (`GMenuItem+0xF0`) points at those meshes.

A glyph does not say what its item does: `GCommandListMenu` panels draw the Cross glyph for Patrol
and the Triangle glyph for Gather. The meaning is the drawing item's. Its `CRender` node is
`workspace+4` at the `GetMatrix` hook and is embedded at `GMenuItem+0x70`; the item carries its
`HotKey` event CRC at `+0x118` and its label C string at `+0x148` (live: `MainBackButton`
`0x012E9540`, `FrontEndBack`, "Back"; `MainSelectButton` `0x012E8A60`, `FrontEndSelect`, "Select").

## PC keys

The keys follow PC RTS conventions (StarCraft): Enter confirms, Esc backs out, arrows navigate, and
every other command takes a letter of its label. `NativePromptKeys` keys each frame's prompts in
draw order:

| item `HotKey` | key |
|---|---|
| `FrontEndSelect` `0x39504A77` | Enter (host Activate) |
| `FrontEndBack` `0xC5AA0E7F`, `MenuTriangle_Release` `0x2E16A928` | Esc (host Cancel) |
| none | Cross glyph Enter, Triangle glyph Esc, else a letter |
| any other (`MenuSquare_Release`, `MenuCircle_Release`, command-panel events) | first letter of the label not yet taken in the frame |

A letter key triggers its item through the item's own registered `GMenuItem::HotKeyActivate`
(`NativeMenuInput::ActivateItem`; surfaceless seam `POST /input/menu-item`). W/A/S/D are not
bound, so the letters stay free.

Esc fires the menu's Back item the same way, as the pad's Back does (`docs/re/input-path.md`).
Calling `GMenu::Cancel` with no item instead left Load/New Profile undrawn after Esc from Load
Profile; live, Esc now returns from Load Profile to a drawn Load/New menu, from Audio to Options and
from the pause menu to the mission, and is refused on Load/New, which has no Back item. The ~30 s
return to the title from an idle front-end menu is the authored `GBaseMenu` `AttractDelay`, re-armed
on every focus change.

In the `avpe` product on Xvfb, real Enter/Esc key presses (xdotool) drove the profile menus and the
key caps read Enter over Select and Esc over Back, covering the glyphs. A windowed control test
(`run_control_test.py --window`) captured the M1 pause menu with caps over both glyphs.

Live in the Marine M1 pause menu, `/prompt/placement` keys Back `back` (item `0x012E9540`) and
Select `confirm` (item `0x012E8A60`); with focus on Resume, `POST /input/menu-item` on the Back item
dispatched its `HotKeyActivate` (`0x00120F40`) and the pause menu closed.

Button glyphs also appear inline in text: `TheFont` (CRC `0x519EE0DF`) maps bytes `0xA9..0xB4` to
Square, Circle, Triangle, Cross, R1, R2, L1, L2 and the four d-pad directions. `TitleFont` maps
`0xAC` to the registered sign, so the byte alone is not an identity. The tutorial strings and "Press
\xAC to Skip Intro" use these codes.

## Dead ends

- A Qt sibling overlay: the render surface is a native child window and stacking is not portable;
  additive text would leave the PS2 glyphs visible. PCSX2's prompt font and ImGui OSD are unrelated.
- A different `GetMatrix` implementation for the prompts: they use `CMeshWorkspace::GetMatrix`.
- Unarmed correlation: one mission frame issues 448 dispatches; the observer must be armed with the
  two resource addresses.
- A 22 px offset carrier (draw-path translation, vertex data, GS registers, 448-vs-480 viewport
  scale): all measured or decoded as absent; the 22 px was snapshot stretch plus the VU1 `-8`.

## Remaining gap

- The title still reads "Press START button". It is TBD string symbol CRC `0x9BD83674` in the
  `CTbdFixupManager` symbol table (element `{value, crc, ...}`), whose value points into the loaded
  `background.tbd` data; the text is not plain in `TBD/TBF.TBF`, whose packing is not decoded.
  Memory-card and load-error messages ("... Press START button to continue") sit in a separate
  string table. Replacing them needs the TBD symbol load path traced so a PC text owner can swap
  symbol values at load.
- Letter commands do not dispatch on the order panel. Live (Marine M1, R2 held), placement keys
  Follow `F`, Waypoint `W` and Patrol `P` on the right `GCommandListButton` items
  (`GGuardButton`/`GWaypointMoveButton` vtables `0x0035ACA0`/`0x0035ABA0`, text at `+0x148`), but
  `POST /input/menu-item` is refused: no navigation menu is active, and the buttons register no
  input callback. `GMenuItem::AttachHotkeys` (`0x00120E60`) registers only when
  `flags(+0x10C) & 0x2010 == 0x10`; these read `0x400C`. `GCommandListMenu::ItemActivated`
  (`0x0027B3B0`) executes the order by item id. The pad's route (R2 plus a face button through
  `GInGameMenu`) is not traced; the letter must call that same route.
- Inline font glyphs (`TheFont` 0xA9..0xB4) are not replaced.
- Bindings are a fixed table in `HostMenuBindings`; they are not yet user-configurable.

## Resolution

Not resolved. Every glyph-mesh prompt is covered by a PC key cap keyed by its item; the gaps above
remain.
