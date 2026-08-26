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
  GAvPPointer::SetInputType     001b18e0  type 1 => absolute + optional Center(); stores @+0x89
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

## Injection plan (shim v1)

- EE-call shuttle on VM thread between frames: save regs, set a0/a1 + pc=fnVA,
  ra=sentinel, run until sentinel — reusable for ANY discovered fn.
- Mouse move → `UpdatePositionAbsolute(pThe__11GAvPPointer deref, {x,y})`
- LMB down/up → PressMouse1/ReleaseMouse1; RMB up → ReleaseMouse2 (all with a1=nullptr)
- Fallback/comparison path: raw writes of pos fields + forced selector method.

## Verification gates

- [ ] Dynamic: confirm active selector mode during gameplay (read ptr+0x344? [+0x89*4])
- [ ] Shuttle call of GetResolution returns plausible values on real boot
- [ ] Injected delta moves cursor on screen (screenshot A/B)
