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
2. VU1 microcode. **Superseded — the microcode is in the ELF**, see the section below. The claim
   recorded here, that `0x3C6690/94/98/9C` and `CWindowData+0x1E8..0x1F4` are never read by any EE
   instruction, was **wrong**. They are interior fields of `VertexWorkSpace[0]` at
   `+0x8B0/+0x8B4/+0x8B8/+0x8BC` (`0x3C5DE0 + 0x8B0 = 0x3C6690`), and `CalcInternalViewport`
   (`0x001761A0`) reads all four **through the workspace pointer**: `lwc1` at `0x8B8`/`0x8BC`
   @`0x001761D4`, `0x8B4` @`0x001761F0`, `0x8B0` @`0x001761F4` and `0x0017620C`. An address-based
   reference sweep reports "no readers" for an address that is interior to a known array, so the
   original conclusion was an artifact of the search method, not a property of the binary.

One further correction: `GetResolution` (`0x00137B30`) returns 640 × **448** (`0x1C0`), not 640 ×
480. `PlatformInit` confirms `FRAMEBUFFER_Init(0x280, 0x1C0)`, while `BeginLayer` normalises the
layer rect against 480. That 448-vs-480 mismatch is real and worth chasing independently, though
it yields 16 or 32 rather than 22.

### The GS packet layout is now decoded, and it explains none of the offset

The `0x6C..` words are **not** GIF packet headers, which resolves the contradiction noted earlier
(`N = 0x6C` implied 109-110 words, impossible in a 224-byte buffer). The real header is the
`0x5000000D` word at byte 0, and the packet is:

```text
+0x00  dword  GIFtag   { NLOOP:15 | EOP:15 | ... }     NLOOP counts 16-byte units
+0x04  dword  DMA chain "next" pointer (0 terminates the chain)
+0x08  dword  REGS[0]   A+D descriptor slot
+0x0C  dword  REGS[1]   A+D descriptor slot
+0x10         data: NLOOP x 16 bytes
```

Size = `16 + NLOOP*16`, checked against four independently-constructed packets with zero slack: the
mesh draw packet (`0x5000000D`, NLOOP 13, `ClaimDMABuffer(0xE0)` = 224), the sprite-vertex packet
(`n*0x30+0x10`), the light-bucket block (`0x60000018`, NLOOP 24, 400 bytes), and `ProcessSprites`
(`0x10000005`, NLOOP 5, `0x60` = 96).

The `0x6C..` words are 32-bit **A+D register-write descriptors**: bits 31-24 select the variant
(`0x6C` normal, `0x6D` terminating), byte 2 is the count in 64-bit units, bit 15 `0x80` marks a
64-bit write, and the low 7 bits are the A+D register number. They tile the packet exactly:

| word | A+D reg | register | count | covers |
|---|---|---|---|---|
| `0x6C028000` | `0x00` | **PRIM** | 2 | bytes `0x10`-`0x2F` |
| `0x6C0B801A` | `0x1A` | **PRMODECONT** | 11 | bytes `0x30`-`0xDF` |

`2 + 11 = 13`, which is the header's NLOOP. No gap, no overlap, and the last dword actually written
(`0xDC`) is the last byte the descriptor covers.

**This refutes the XYOFFSET speculation.** XYOFFSET is A+D register `0x18`/`0x19`; the descriptor
says `0x1A`. A whole-image scan of the engine's GS vocabulary (26,755 constants tracked across
481,169 instructions) finds **no** `0x18`, `0x19`, `0x1B` (PRMODE), `0x40` or `0x41` (SCISSOR)
descriptor anywhere. The draw path never writes XYOFFSET or SCISSOR at all. `0x6C028000` is PRIM,
whose payload is a VRAM primitive-list pointer and two control words, not a numeric transform.

And the scale reading is settled by the value rather than the register identity: the leading payload
of the `0x1A` block is `(0, 1.0f, 0, 0)`, where `1.0f` is a hard `lui $t0,0x3f80` literal in all
three construction sites. **A scale-based explanation for the 22-pixel offset is ruled out.**

So no GS register write in this packet set produces a pixel-space offset. The 16-float model matrix
*is* shipped, at bytes `0xA0`-`0xDC`; `SFXTileDraw` hardcodes it as the literal identity. Combined
with the CPU transform having no 22-pixel term and `PS2ProcessVerts` doing no coordinate math, the
displacement is narrowed to VU1 microcode or the vertex data itself.

One caveat, recorded so it is not mistaken for a settled result: the `0x1A -> PRMODECONT` identity is
high-confidence but **not proven**. A strict auto-increment chain from `0x1A` would place the 4x4
model matrix on `FBA`/`FRAME`/`ZBUF`, which is self-evidently wrong, so either the descriptor's
coverage is not a pure register chain or `0x1A` is not PRMODECONT. That is the weakest link in the
decode and it does not affect the conclusion above, which rests on the absence of XYOFFSET/SCISSOR
and on the literal `1.0f`.

### The VU1 microcode is in the ELF — the transform is obtainable

The blocking assumption was wrong: the microcode is **not** absent. It is embedded in the loaded
image, with the original assembler's own local labels intact in the ELF symbol table.

- **VU1 code: `0x002CEF80` (`_$entry`) … `0x002D1538` exclusive — 9656 bytes.** Labels inside it:
  `_$kick_it`, `_$no_kick`, `_$scissor`, `_$code_mesh`, `_$comp_verts`, `_$mesh_loop`,
  `_$spriteloop`, `_$code_sprite`, `_$offscreen`, `_$code_background`, `_$colour_loop`,
  `_$batch_loop`, `_$nothing_to_flush`.
- **VU0 code is a separate blob: `vu0Math` at `0x002D17A0`…`0x002D18B4`, 272 bytes**, containing
  `_$vu0SinCos`, `_$vu0ATan2`, `_$vu0MatrixMult`, `_$vu0SetEuler`.
- Both sit inside static DMA/VIF/GIF packets alongside macro-generated labels (`.dma.NN`,
  `.vif.NN`, `.gif.NN`) from the assembler's macro package — `.dma.1` appears twice, once per
  expansion, at `0x002CEB00` and `0x002D17A0`.

**The upload is EE-driven over DMAC channel 1, in chain mode, once per frame.** There is no
`InitVu1`; the load is fused into `EndFrame__8CRendAPIFv` (`0x00178B00`), which pushes 16 bytes into
the VIF1 in-FIFO at `0x10005000`, calls `FlushTextureBuffer__Fv` (`0x00188290`), then sets
`QWC = 0`, `TADR = 0x003C9FC0`, `STAT = 2`, `FlushCache(0)`, `CHCR = 0x145`. The chain head is built
by `BeginFrame__8CRendAPIFv` (`0x00178970`) as two nodes — `&SpriteMeshDMA` (`0x002CEB00`,
675 QWC = 10800 B, spanning the VU1 blob) and `&GateTexture` (`0x002D15D0`, 28 QWC = 448 B) — plus a
terminator. The clearest statement of the load idiom in the whole image is the VU0 analogue,
`InitVu0MathLib__Fv` (`0x0017AC70`), which does the same five stores against channel 0 with
`TADR = 0x002D17A0`.

This also **explains, or rather fails to explain, the four globals.** `SetOutputScales`' writes to
`0x003C6690/94/98/9C` and the `CWindowData+0x1E8..0x1F4` fields derived from them were recorded here
as being consumed only by VU1. **That was wrong** — they are interior fields of `VertexWorkSpace[0]`
and `CalcInternalViewport` reads them on the EE. What survives is weaker but still useful: they are
depth-precision and sub-pixel scale factors (`+0x1E8 = 32.0/halfWidth + 1`,
`+0x1EC = 16.0/halfHeight + 1`, and two large z-scale terms), so they carry no screen placement and
no 448 or 480. The precise decode, from raw `swc1` bit patterns:

| written | bits | as float |
|---|---|---|
| `ws+0x8B0` (`0x3C6690`) | `0x4B7FFFF0` | 16777200.0 (= 2²⁴ − 16) |
| `ws+0x8B4` (`0x3C6694`) | `0xCAFFFFF0` | −8388600.0 (= arg1 − arg0) |
| `ws+0x8B8` (`0x3C6698`) | `0x42000000` | 32.0 |
| `ws+0x8BC` (`0x3C669C`) | `0x41800000` | 16.0 |

Every alternative provenance was ruled out with a stated method:

| hypothesis | verdict | method |
|---|---|---|
| microcode file on disc | **ruled out** | full printable-ASCII extraction of all initialized blocks (35,973 strings). The only `cdrom0:` paths are `IOPRP242.IMG`, the seven IRX files, `TBD\`, and `MOVIES\`. No `.bin`, `.vu`, `.code`, `.irx` or microcode-named string exists anywhere |
| an IOP service carries it | **ruled out** | `sceSifInitRpc` is called once, from `PS2_PlayMovie__FPci`. The `sceSif*`/`sceDma*` symbols at `0x002AAEA8..` are the IOP-side `libdma`/`libetc` linked into the EE ELF, and `sceDmaOpen`/`FastNext`/`Sync`/`Close` do not exist in this ELF at all |
| an IRX owns VU loading | **ruled out** | the seven IRX files are SIO2, pad, libc, SD, memcard and FSSOUND; `IOPRP242.IMG` is the stock IOP reboot image. None is a graphics module |
| generated at runtime | **ruled out** | the EE never forms a VU address at all — a `lui` immediate sweep over all 481,169 instructions gives 0 hits for `0x1100` and 0 for `0x1F80`, and a raw byte scan of all 4,829,548 bytes gives 0 hits for `0x11008000` |

Two register-map notes, because they invalidate an obvious search method. Hardware is reached at
**`0x1000xxxx`**, never `0x1F80xxxx`, so scanning for the retail `0x1F80xxxx` operands finds
nothing; addresses are built with `lui`+`ori` **or** `lui 0x1001` plus a *negative* `sw` offset, so an
`ori`-backreference census under-counts and misses sites. Separately, the DMAC channel stride here
is `0x1000` where the retail map uses `0x10`. Whether this build was linked against a modified
ps2sdk base is unresolved; the channel assignment itself is self-consistent and corroborated by
which blob each channel loads (ch0 → VU0 labels, ch1 → VU1 labels).

Still undecoded, and the immediate next step:

1. **How the `.vu` words reach VU1 *code* memory.** No VIF1 DMAME tag with a code-memory mode bit was
   found, and DMAC1 MADR is never given a VU address — MADR is written only at five sites, all
   inside the IOP-side `libdma` blob. The likely control is the `0x00008006` word `EndFrame` pushes
   into the VIF1 in-FIFO every frame, from `disable_path3$859` at `0x002D6F10`. **Undecoded.**
2. **The VU1 instruction stream itself.** 16-byte cadence, but `0x002CEF80 → _$kick_it` is `+0x88`
   (136 B), which is not a multiple of 16 — so instruction boundaries are not yet certain. Disassemble
   `0x002CEF80..0x002D1538` with a real VU1 disassembler before assuming offsets.

With the microcode located, the remaining work is a decode rather than a search, and the y-flip and
viewport scale must live in `_$comp_verts` or `_$mesh_loop`.

### Screen placement is 448 tall, and 480 is the projection box

`GetResolution__9CRendererFv` (`0x00137B30`) is a two-instruction thunk to
`GetResolution__8CRendAPIFv` at `0x00178930`. It stores `0x280` and `0x1C0` to `0x003C9FE8` and
`0x003C9FEC`, so it returns a **RECT `{0, 0, 640, 448}`**, not a width/height pair. Every consumer
subtracts the first two fields from the last two and treats 448 as the bottom of the screen.

**448 is authoritative for screen placement; 480 is the projection box.** That is settled by the
guest's own arithmetic, not by plausibility:

- `sceGsSetDefDrawEnv` centres the buffer as `2048 − height/2`, which for 448 gives a Y-offset of
  **1824**. A 480-tall buffer would give 1808. `FRAMEBUFFER_Init` (`0x0017D0E0`) has exactly one
  caller, so 448 is never revised.
- The menu pointer centres at **`(320, 224)`** — the exact centre of a 448-tall screen. A 480-tall
  screen would have produced 240.
- The FPS HUD is bottom-anchored at **`y = 431`** = 448 − 17. A 480-tall screen would have given 463.
- Pointer clamping (`Clip2Screen`), link/unlink, selection rect and **screen-bbox culling** all use
  `[0,640] × [0,448]`. In `CMeshWorkspace::GetMatrix` a box whose `maxY` exceeds 448 is culled.
- 448 is the NTSC visible height (480 − 32 blanking), and `sceGsSetDefDispEnv` contains ps2sdk's
  underscan compensation, which only makes sense if 480 is the signal and 448 the visible window.

So a host overlay should be placed in `[0,640] × [0,448]`, y increasing downward, origin top-left.

**There is a real 32-line inconsistency, and nothing in the guest resolves it.** `BeginLayer`
(`0x00179220`) normalises the layer rect against 640 × **480** and calls
`SetViewport(0, 0, 640, 480, …)` every frame for every layer; `ShellLoadLevel` separately calls
`Ortho(0, 640, 480, 0, 0, 1000)` for layer 7; and `GOrdering3dDisplay` divides absolute pixels by
640 and **480**. Meanwhile `SetViewport` (`0x001754D0`) range-checks only the layer index and
performs **no clamping** of x/y/w/h, and `CalcScreenMatrix` builds the screen matrix from the
viewport half-extents with no clamp either. **Content with screen y in (448, 480] is therefore
generated and not clipped by any EE code** — it simply has no pixel underneath it, because the GS
draw area is set once from 448.

One residual risk, stated rather than hidden: which GS register does the clipping is not settled from
EE code, because the register packing lives inside ps2sdk's `sceGsSetDefDispEnv`/`SetDefDrawEnv`
boilerplate. "Draw area is 448, so the bottom 32 projection lines are dropped" and "480 with a
448-line display window, so nothing is lost and the TV crops" are both consistent with everything
read from the EE. The visible extent is 448 either way, so the recommendation above stands; a
runtime dump of `GS_DMODE` (SCAX1/SCAY1) and `GS_DISPLAY` (DWIDTH/DHEIGHT) would settle which.

Also corrected: `CWindowData+0x1C4` is **640.0** (`0x44200000`), not 1024.0. An earlier pass
misdecoded that float; exponent field `0x88` with mantissa 1.25 gives 640.

### How the microcode reaches VU1 — mostly settled, with one honest gap

**Read the ELF little-endian.** `readelf -h` reports `Data: 2's complement, little endian`, and
every static word must be read as a LE `u32`. Big-endian reads produce `0xA3020060`,
`0x1C000060`, `0x11000010` and an unparseable stream. Confirmed three independent ways:

1. Read as LE, the DMAC tag lengths **tile the region with zero slack** — `0x2CEB00` → 675 QWC →
   next tag exactly `0x2D1540` → 8 QWC → exactly `0x2D15D0` → 28 QWC → exactly `0x2D17A0` → 17 QWC
   → `0x2D18C0` = `0x70000000` (`TAG_END`). Big-endian makes those MARK fields `0xA`, `0x1C`,
   `0x11`, which are invalid.
2. CPU-written tags read back identically under the same convention: `BeginFrame` stores the `u32`
   `0x50000000` with `sw`, which must decode the same way a static word does.
3. The symbol at `0x002D6F10` is named `disable_path3`, which only means anything if the word is
   `0x06008000` — VIF1 command `0x06` = **MSKPATH3**. Big-endian it is `0x00800006`, a plain NOP,
   and a NOP is never named `disable_path3`.

This is the single biggest trap in the whole reverse-engineering effort, and it is worth recording
because it invalidates any search whose output depended on byte order.

**The 16 bytes at `0x002D6F10`** are `0x06008000` followed by three zero words: one **MSKPATH3**
with `mskpath3 = bit15 = 1`, masking GIF path 3, then three NOPs. It is **not** a memory-address-mode
tag — bit 31 is 0, so `DMAME` is ruled out. `EndFrame` pushes it with a single 128-bit write to
`VIF1INIRQ` at `0x10005000`.

**The DMAC chain-tag layout is reconciled.** It is the ordinary PS2 source-chain tag with `MARK` in
bits 28-31, the count or address in bits 0-15 of word 0, and the jump address in word 1; words 2-3
are payload transferred only when `CHCR.TTE = 1`. That resolves the earlier contradiction where
`0x50000000` appeared where a pointer was expected and `0x600002A3` where a length was: `0x50000000`
is **TAG_CALL with QWC 0** (pointer in word 1, closed by a TAG_RET at the callee) and `0x600002A3`
is **TAG_RET with QWC 675**. `CHCR = 0x145` sets `ASP = 1`, which is what makes CALL/RET legal.

**One mechanism remains undetermined, and it is recorded as such.** The only VIF1 command in this
emulator that writes VU *code* memory is `vifCode_MPG`, command byte `0x2D`. A word-aligned scan of
the 675-QWC body finds **no such command**, and a scan of the whole image finds every apparent hit
inside MIPS code or inside ASCII strings (`0x2D6D10` is the text `"2D6E6F6E"`). The apparent
byte-level hits are unaligned coincidences. So no EE code writes a VU1-code-write tag, and only one
static `VIF1INIRQ` push exists in the entire image. The blob is certainly carried in the per-frame
`SpriteMeshDMA` payload, but **which word routes it into code memory is not determined.** Either
AVP:E relies on a VIF1/DMAME mode that this PCSX2 does not implement, or the real upload comes from a
runtime-built packet that was not located. Not asserted either way.

**The microcode is re-sent every frame, unconditionally.** `BeginFrame` rewrites the chain head at
`0x003C9FC0` each frame and `EndFrame` restarts VIF1 DMA each frame, so 10800 B — of which 9664 B is
the VU1 program — is pushed into the VIF1 in-FIFO every frame. `CHCR` bit 7 is also set, which on
hardware is `CHRTE` (cycle repeatedly); this PCSX2 misnames that bit `TIE` and does not implement
`CHRTE`.

**Register-map corrections**, taken from this tree's authoritative `Hw.h`, which invalidate earlier
guessed labels:

| address | actually | earlier guess |
|---|---|---|
| `0x10003010` | **GIF_MODE** (CTRL `0x10003000`, STAT `0x10003020`) | DMAC MADR |
| `0x10009000` | **VIF1** CHCR (MADR `…010`, QWC `…020`, TADR `…030`) | "DMAC1" |
| `0x10008000` | **VIF0** CHCR — what `InitVu0MathLib` uses for the VU0 upload | "DMAC0" |
| `0x10003C00` | **VIF1_STAT** | DMAC |
| `0x10002000..30` | IPU | DMAC |

`0x10009000` being VIF1 is confirmed behaviourally: `sceGsExecStoreImage` (`0x002AA758`) drives it
while polling `VIF1_STAT` and pushing `VIF1INIRQ`.

### The GS configuration is exonerated too — the two paths are pixel-identical

Decoding `sceGsSetDefDispEnv` (`0x002A97A0`), `sceGsPutDispEnv` (`0x002A9A10`, which gives the
decisive struct→register map), `sceGsSetDefDrawEnv` (`0x002A9B98`) and `sceGsResetGraph`
(`0x002A9598`) settles the GS side completely.

**Two hypotheses from the brief are dead, and they were the load-bearing ones:**

- **`env+0x10` is `DISPFB`, not `DMODE`.** `sceGsPutDispEnv` shows `param_1[2]` →
  `REG_GS_DISPFB1/2`, and ps2sdk's `GS_SET_DISPFB` puts `FBW` at bits 9-14 and `PSM` at 15-19 — an
  exact match. **The GS drawing-area enable bits are never written by this title**, and `CSR = 0x200`
  (`wRESET`) at `sceGsResetGraph` leaves them 0. There is no drawing-area masking at all.
- **`DISPLAY` never reaches the rasteriser.** Its `DX/DY/DW/DH/MAGH/MAGV` feed only
  `GSState::GSPCRTCRegs::SetRects()`, i.e. the CRT/upscaler model — never `ConvertVertexBuffer()`,
  the scissor, or `m_xyof`. Values read: `DX=641`, `DY=50`, `MAGH=3` (×4), `MAGV=0` (×1), `DW=2559`,
  `DH=446`, with `PMODE=0x83`, `SMODE2=0x2`, `SCISSOR_1 = 0x01BF0000027F0000` (SCAX0=0, SCAX1=639,
  SCAY0=0, SCAY1=447), `FRAME_1` FBP=0/FBW=10, `ZBUF_1` ZBP=280.

**The only coordinate-relevant register is `XYOFFSET_1 = 0x0000720000006C00`**, computed from the
shifts at `0x002A9C74`-`0x002A9CB4` as `(0x800 − w/2) << 4 | (0x800 − h/2) << 36`, giving
`OFX = 27648` and `OFY = 29184`. The guest confirms it independently: `sceGsSetDefClear` emits a
clear sprite whose vertex sits at exactly `(OFX << 4, OFY << 4)`, so the game itself places the
framebuffer origin there.

So the complete GS-side transform is:

```text
framebuffer_x = vertex_X/16 − 1728
framebuffer_y = vertex_Y/16 − 1824
```

**No y-negation, no flip, no scale beyond the fixed 1/16, and no additive constant.** (Note the
field packing: each axis is a *flat* 16-bit value in 1/16-pixel units — ps2sdk's
`GS_SET_XYOFFSET` and pcSX2's `XYOFFSET_REG_MASK 0x0000FFFF0000FFFF` agree, and the widely-cited
nibble-split description is wrong for this title.)

**The decisive comparison.** `OFY/16 = 2048 − 1824 = 224`, which is *exactly* the `vh/2 = 224` the
CPU-side `TransformPoint` adds. So:

```text
CPU:  ScreenY = n_y·(vh/2) + (y0 + vh/2) = n_y·224 + 224
GS :  y_px    = n_y·224 + 224                            (from XYOFFSET/16)
Δ = 0 for every n_y
```

**The guest's model→screen transform and its GS configuration are the same function, pixel for
pixel.** No combination of `DISPLAY`, `SMODE2`, `DISPFB`, `FRAME`, `ZBUF`, `SCISSOR` or `XYOFFSET`
yields 22 pixels (22 px = 352 in 1/16 units; nothing equals 352). The 480-vs-448 ortho was checked
numerically too: `yd ∈ {0, .25, .5, .75, 1}` gives `Δ = 0.000` at every point, because both are
centred — a height mismatch produces a *scale* error growing with `|n_y|`, never a constant.

### What is left, stated precisely

Every carrier is now eliminated except one. A **constant** 22-pixel displacement requires a constant
added on the model→pixel path, and the only structure in the whole chain that carries a
draw-path-only translation the culling path never reads is the model translation `PS2ProcessVerts`
ships to VU1:

```c
puVar7[0x1C] = fVar25 + fStack_174;   /* (float)piVar9[0x15]  -> packet byte 0x70 */
puVar7[0x1D] = fVar20 + fStack_178;   /* (float)piVar9[0x16]  -> packet byte 0x74 */
```

`piVar9` is the per-primitive parameter record, and `GetScreenBoundingBox` never looks at it — it
uses only `mesh+0x1C..0x30` and the matrix stack. So the draw path sees a translation the culling
path does not.

**This makes the next step exact, and it is not the one originally recorded here.** Instrumenting
`PS2ProcessVerts` is still right, but for the opposite reason: not to capture a final screen
coordinate — it computes none — but to read `piVar9[0x15]` and `piVar9[0x16]` for the Select and
Back submeshes at draw time. If the second is ±22.0, the prompt placement closes with no magic
constant. If it is zero, the offset is in the vertex array itself, and the only remaining route is
to compare the vertex Y values against the stored bbox corners for the same draw.

### A mechanism that yields exactly 22 pixels — found, and testable

`ViewportData` (`0x002CEBD0`) is a **write-only CPU→VU1 parameter block**: nine 0x60-byte slots,
patched per frame by `EndFrame__8CRendAPIFv` (`0x00178B00`) *before* the channel-1 kick at
`0x001791AC`, and contained inside the per-frame DMA span (`0x2CEBD0 − 0x2CEB00 = 0xD0`, well inside
the 4112-byte transfer). It lands in VU1 data memory at `VU1_off = guest − 0x2CEB10` via
`VIF_UNPACK V4-32` at `0x002CEB0C`.

Per-slot contents, read from the binary: floats 0-15 are `projection * camera`; 16-17 are the
viewport half-extents; 18/22 are depth terms; 19/23 are `WD[0x40]*WD[0x1D4]` and `WD[0x54]*WD[0x1DC]`;
and **20-21 are the GS draw-env origin**:

```text
float 20 = 1728.0 + (w*0.5 + left)        1728 = 2048 − 320
float 21 = (1824.0 + (h*0.5 + top)) − 8.0  1824 = 2048 − 224, less a hard-coded 8
```

**The mechanism is the 448-vs-480 mismatch, and it is the only one in the binary that yields 22.**
`BeginLayer__8CRendAPIFi` (`0x00179220`) scales normalised layer rects **X by 640 and Y by 480**
(`0x44200000` and `0x43F00000`, each built in exactly one place), while the framebuffer is 640 ×
**448**. Horizontal scale matches; vertical does not:

```text
guest_y   = v · 480
correct_y = v · 448
error     = v · 32 = v / 14
```

Setting `error = 22` gives `v = 308`, a layer fraction of `308/448 = 0.6875 = 11/16`, and
`32 × 11/16 = 22` **exactly**. Nothing else in the block can do it: the draw-env path gives at most
**−8 px**, the packed rect path's `−16` insets plus clamps give at most **18 px**, and `fptosi`
truncation at most 1 px.

A decisive negative supports the emergent reading: **`480.0f` is built in exactly one place in the
whole image** (`0x00179284`, `BeginLayer`), and **no `22.0f` exists anywhere**. So 22 is not a stored
constant — it falls out of 480-vs-448 applied at the right position.

**This is the discriminator to run.** Dump `Layer->f[4]`/`f[5]` (the rect floats at `layer+0x10` /
`+0x14`) for the prompt's layer, or `CWindowData+0x1C8`/`+0x1CC` (`0x3C6868`/`0x3C686C`) after
`BeginLayer`. If either is 308, or the fraction is `11/16`, the mechanism is confirmed. The prompt's
**top** field is the one to read: the bottom edge is hard-capped at 448 after its `−16` inset so it
can carry at most 16 px, while the top edge's floor is 0 and its ceiling is unclamped, so it can carry
the full `v/14`.

**Not yet confirmed for the prompts specifically.** The mechanism produces exactly 22 px and nothing
else does, but whether the prompt layer sits at `11/16` is a runtime fact, not a static one. If the
dump disagrees, the remaining candidates in priority order are: `piVar9[0x16]` being ±22.0 for those
submeshes (the draw-path-only model translation, still the single uneliminated structural carrier),
then the vertex array itself differing from the stored bbox corners.

A broader consequence worth checking separately: if layer rects are scaled against 480 while the
buffer is 448, then **every** HUD or overlay element positioned through a layer rect is displaced
downward by `y/14`, not just the prompts. At `y = 308` that is the full 22 px; near the bottom of the
screen it approaches the full 32 px of overscan. Whether that is a game bug or intentional NTSC
overscan-safe authoring — the guest selects NTSC interlaced, with `DHEIGHT = 446` — is not resolved,
but it should be checked before any host overlay is anchored to a guest-authored layer rect.

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