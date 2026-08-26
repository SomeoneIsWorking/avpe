# AVP:E input path — RE findings

Target: `SLUS_201.47` (USA, NTSC, 2003-04-29). ELF not stripped: `.symtab` ~15k syms.
Ghidra project `scratch/ghidra/AVPE`, program analyzed as **r5900:LE:32:default**
(ghidra-emotionengine-reloaded v2.1.37 installed into Ghidra 12.0.4). Generic-MIPS
import garbles MMI code — do NOT re-import without `-processor r5900:LE:32:default`.

## Architecture

```
CPS2Input : COSInput            (libpad poller; ctor 0017dc50)
  PollDevices     0017dde0      scePadGetState/Read/InfoMode/SetMainMode state machine
  GetControlValue 0017e220      generic accessor (digital + analog)
  per-port struct stride 0x50 at this+0x414:
    +0x40c flags, +0x414 last state, +0x41c prev paddata[32],
    +0x43c..43d buttons (active-low), +0x440..443 rx ry lx ly (0x80 center)

GPS2InputDevice : GInputDevice  (device object; GInputDevice::Process = dispatcher)
  Process         00114490      polls backend via vtable+8/+0xc, walks
                                ZArray<CCallbackTrigger>, edge-detects, __ptmf_scall's
                                registered member fns with a CInputData built on stack
  Register(name)                binds named trigger -> (object, ptmf)
  LoadGamepadTbd  00114380      physical->logical map from .tbd data file

GfsPointer (base) / GAvPPointer (game cursor, singleton pThe__11GAvPPointer @ 00367720)
  Input_UpdatePosition          0012e9f0  RELATIVE: pos += cdata[0..1]*10000.0f, Clip2Screen
  Input_UpdatePositionAbsolute  0012eab0  ABSOLUTE: pos = cdata[0..1] (screen px),
                                           unlink if outside CRenderer::GetResolution rect
  Input_Action/ActionUp         0012ebb0/0012ec10
  SetSelectorMethod             0012da50  0=relative, 1=absolute selector
  GAvPPointer::SetInputType     001b18e0  type 1 => absolute + optional Center(); stores @byte+0x224
  GAvPPointer::Center           001b1990  pos = resolution center
  Input_PressMouse1             001b52c0  SelectChanging(this,1,0)   [ignores CInputData*]
  Input_ReleaseMouse1           001b52d0
  Input_PressMouse2             001b5300  EMPTY BODY
  Input_ReleaseMouse2           001b5310  CommandMove(this, vec@00302680)
  RegisterInput                 001b4f90  registers 6 named triggers (names below)
  Process                       001b1aa0  selection logic over ZArray<GMarkSelect>

Trigger names (strings @ 0x2e1810..): PointerUpdatePosition,
PointerMouseButton1Activate/DeActivate, PointerMouseButton2Activate/DeActivate.
ptmf table @ 0x2e17a8, stride 0x10.

Singletons (OBJECT syms): pThe__11GAvPPointer 00367720, pThe__12GInputDevice 00366e68,
pThe__9CRenderer 00367078. CRenderer::GetResolution 00137b30 returns float[4]
(x0,y0,x1,y1) used for pointer clamp.

Pointer position fields: this+0x194/0x198 (ints idx 0x65/0x66, float semantics);
+0x188/0x264 mirror copies written by SetInputType.

`CInputData` prefix consumed by `Input_UpdatePositionAbsolute`: f32 `x` at
`+0x00`, f32 `y` at `+0x04`; no instruction in that function reads beyond
`+0x04`. The earlier decompiler index for the input-type field was
`int[0x89]`, which is byte offset `this+0x224`, not byte offset `+0x89`.
```

## Key conclusions

1. Engine has a NATIVE absolute-pointer mode (`SetInputType(1)` / `SetSelectorMethod(1)`
   and `Input_UpdatePositionAbsolute` taking raw screen pixels). No need for any
   pad-axis emulation: drive these directly.
2. All four mouse handlers ignore their `CInputData*` argument — safe to invoke with
   nullptr once we can execute EE calls.
3. Right-click command fires on RELEASE (CommandMove); left click is press+release pair.
4. Camera also switches pointer input type (`Input_GPMove` calls SetInputType twice) —
   dynamic phase must verify which mode is active in-game before injecting absolutes.

## Camera / squad / minimap (batch #5)

```
GAvPCamera ctor 001aded0; singleton pThe__10GAvPCamera @ 003676f0
Input_GPMove   001af140  cdata[fx,fy] -> camera Move; calls Input_GPPosition on pointer;
                         if bGamePadMouse==0 -> SetInputType(1,1)+Move, else SetInputType(2,1)
                         also MiniMapMode(false) + bMoveRotationMode rotation branch
Input_GPRotate 001af240  Input_GPZoom 001af480: zoom = MiniMapMode(1) +
                         MoveCamPointerPos (minimap camera pointer pan), or Gyrate
CommandMove    001b3a50  builds msg {id=0x60039,type=5} + vec -> squad dispatch
Move           001b3c50  reads selection array through pointer+0x1b0, dispatches
                         the move message to one unit or a synthesized squad
MakeSquad      001b1f50  from ZArray<GMarkSelect> selection
SendMessageToSquad 001b22a0
GSelectMenuButton::HotKeyActivate 0027caa0 menu click path:
                         SelectChanging(false,...) + SetInputType(0,0) + Refresh

Globals: bGamePadMouse @ 003676f4 (gamepad-mouse cursor mode flag),
bMoveRotationMode @ 00368850, pThe__8GMiniMap @ 00367f40.
```

SC-style control mapping now fully RE'd: move=absolute pointer inject,
LMB=Mouse1 pair (SelectChanging), RMB release=ReleaseMouse2(CommandMove),
pan/zoom=minimap cam pointer, groups=MakeSquad/SendMessageToSquad.

## Native menu actions

`GInputDevice` stores its live `ZArray<CCallbackTrigger,32>` at `this+0x48`
(`data` at `+0`, count at `+4`; entries are `0x18` bytes). A callback entry
stores its owner handle at `+0x08` and direct ptmf function at `+0x14`.
Callbacks for `GMenu::InputUp/Down/Left/Right/InputAnalog` identify the unique
active menu owner; handle resolution uses `GObject::TheHandleArray` at
`0x00371020`.

`GMenu::Input` is `0x00125330`; actions are Up=0, Down=1, Left=2, Right=3,
Activate=4. The active focused-item handle is `menu+0x26c`. Returning
directional calls are safe through the EE-call transaction and changed pause
focus from Resume to Save. Activate is not safe through that boundary: on the
Press START item it exceeded both 3M and 30M cycles because shell/menu ownership
can be replaced before the synthetic call returns. Native activation must be
queued onto AVP:E's ordinary input/update execution path.

## Native bridge

- `NativeInput::MoveAbsolute` accepts normalized coordinates, validates the
  live pointer and resolution, reasserts absolute selector mode, and calls
  `UpdatePositionAbsolute(pThe__11GAvPPointer deref, {x,y})`.
- The EE-call shuttle stages the eight-byte `CInputData` in a bounded synthetic
  o32 stack frame, interprets the target call with a distinct jump context,
  restores the interrupted EE/FPU/VU0 context and exact stack bytes, then lets
  the outer scheduler service deferred events. Recursively entering PCSX2's
  recompiler would overwrite its global dispatch jump buffer.
- `NativeInput::ApplyButtonEdge` owns typed primary/secondary press state,
  rejects duplicate or unmatched edges, and invokes the original handler for
  each edge. Savestate load resets the host-held edge state.
- LMB down/up → PressMouse1/ReleaseMouse1; RMB down/up →
  PressMouse2/ReleaseMouse2. The empty RMB-press function is still invoked so
  host edge semantics match the game's registered input sequence.
- The selection owner at `pointer+0x1b0` points to a
  `ZArray<GMarkSelect*,32>` (`data` at `+0`, `count` at `+4`). Each selected
  mark points to its selected game object at `mark+0xa8`.
- `SendCommand__5GUnitFP8CMessagebb` records the accepted message ID at
  `unit+0x460`. Right release produced `0x60039`, the exact move-message ID
  built by `CommandMove`, before the scheduler consumed it.
- Diagnostic comparison: raw writes of position fields demonstrate that the
  screen-position members are not the rendered world-position authority.

## State evidence protocol

The authoritative capability state and verification conditions are S007–S011
in [`../project-state.md`](../project-state.md). Subsystem evidence must include
a real-boot shuttle call of `GetResolution`, a runtime read of the active
selector mode, and frame A/B observations showing that distinct injected
coordinates move the rendered cursor.
S008 is backed by C009 and the trusted two-arc detector I002. S009 is backed by
C010 and I003: the primary pair changed selected object identity, the secondary
pair recorded move message `0x60039` on that same object, invalid edge sequences
were rejected, and the process shut down gracefully.
