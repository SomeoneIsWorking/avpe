# AVP:E input path — RE findings

Target: `SLUS_201.47` (USA, NTSC, 2003-04-29). ELF not stripped: `.symtab` ~15k syms.
Ghidra project `build/ghidra/AVPE`, program analyzed as **r5900:LE:32:default**
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
                                registered member fns with CInputData at device+0xac
  Register(name)                binds named trigger -> (object, ptmf)
  LoadGamepadTbd  00114250      physical->logical map from .tbd data file

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

`GInputDevice::LoadGamepadTbd` chooses the longest matching controller name,
then formats `Gamepad%s.tbd` from its selected `TbdFile` entry before loading
the title resource. Its static table includes `DualShockPS2`, `ThrustMaster`,
`HammerHead`, `HammerHeadUSB`, and `DualShockPC`; the named actions include the
shoulder and cluster-button press actions. This grounds controller-resource
selection, but not a prompt draw: a `.tbd` maps physical controls to named
actions and does not yet identify any on-screen glyph resource or rectangle.

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

The callable camera contracts are now explicit. `Input_GPMove` receives the
same eight-byte `{float x, float y}` prefix used by the input callbacks and
updates camera movement at `camera+0x158/0x15c`; it also calls
`SetInputType(pointer,1,1)` in the normal camera path. `Input_GPZoom` consumes
`x` and, while `camera+0x238` is clear, enters minimap mode and calls
`MoveCamPointerPos(minimap, CVector*)`; that function scales and clamps the
minimap cursor at `+0xbc0/+0xbc4/+0xbc8` and derives the camera pointer at
`+0x250/+0x254`. `Input_GPRotate` uses the same minimap path for `x` or calls
`Gyrate(x,0,0,camera,0)` when camera mode requires it. The native bridge calls
these original functions through the EE shuttle and captures the camera,
minimap, and pointer-mode fields before and after each call.

The standalone host maps held W/A/S/D and arrow keys to the grounded
`Input_GPMove` pair at a 16 ms tick, and the mouse wheel to `Input_GPZoom`.
Menu discovery is attempted first, so the same keys navigate a live AVP:E menu
and become camera controls only when no menu owns them. The control route
`POST /input/camera` is the surfaceless evidence seam for move, rotate, and
zoom; it does not replace the host route.

## Native menu actions

`GInputDevice` stores its live `ZArray<CCallbackTrigger,32>` at `this+0x48`
(`data` at `+0`, count at `+4`; entries are `0x18` bytes). A callback entry
stores its owner handle at `+0x08` and direct ptmf function at `+0x14`.
Callbacks for `GMenu::InputUp/Down/Left/Right/InputAnalog` identify the unique
active menu owner; handle resolution uses `GObject::TheHandleArray` at
`0x00371020`.

The `32` is the array's growth increment, not a callback limit: its `+0x08`
capacity grows by `0x20` records whenever count reaches capacity. The normal
dispatch observer snapshots the live registry at `GInputDevice::Process` entry
`0x00114490`, accepts it only when `count <= capacity`, and resolves every
current owner handle before reporting the `GAttractExit` vtable
`0x00343AF0`. Consequently `attract_registered=false` means a complete valid
registry scan, while any unreadable registry is explicitly invalid rather than
silently treated as absent. This is evidence only; title transition policy
remains guest-owned.

The title's physical Cross route has two guest-owned steps. With the 52-entry
registry, the first Cross dispatches `GAttractExit::Input` at `0x00206A60` and
its normal lifecycle removes that owner, leaving the 8-entry press-start
registry. A second Cross then dispatches the focused `GMenuButton` activation
descriptor `{0, 0xcc, 0}` and creates `GProfileMenu`. The host must preserve
that cancellation sequence; neither its input policy nor a title diagnostic may
skip directly to the profile menu.

`GMenu::Input` is `0x00125330`; actions are Up=0, Down=1, Left=2, Right=3,
Activate=4. The active focused-item handle is `menu+0x26c`. Returning
directional calls are safe through the EE-call transaction and changed pause
focus from Resume to Save. Activate is not safe through that boundary: on the
Press START item it exceeded both 3M and 30M cycles. `GPressStartMenu` routes
the focused button through `ItemActivated` at `0x00209f30`, which calls
`Load__5GMenu`; that path needs the EE/IOP/CDVD events deliberately suppressed
by `ExecuteUntil`. Deferred calls instead exit the current EE block, run under
the ordinary VM scheduler, and force the saved return PC through a completion
hook that restores the interrupted architectural context and reserved stack.

Activation now first traverses the active menu's bounded descendant tree and
finds the unique registered item whose action is `ActivateFocused` and whose
resolved member function is `GMenuItem::HotKeyActivate` at `0x00120F40`. It
queues that original callback owner and descriptor through
`GInputDevice::Process`; it does not overwrite an unrelated menu callback to
make it call the focused item. If no descendant hotkey exists, only the exact
registered active-menu activation callback is eligible. Ambiguous or invalid
owners fail closed.

`POST /input/menu-action` may additionally arm one diagnostic readiness
request with `when_menu_vtable` and `when_focused_item_action`, both exact
eight-digit guest words. `NativeMenuInput` observes only the ordinary
`GInputDevice::Process` entry through `NativeEeExecutionHooks`; it waits
through unrelated menu lifecycles, rejects an invalid candidate for the named
menu owner, and emits one existing physical-pad input when that owner and its
focused action are current. It does not synthesize an unregistered directional
callback, retry after a candidate validation failure, or survive a savestate
load. `GET /input/menu-readiness` reports the one request as pending,
dispatched, rejected, or absent.

`GMenu::Cancel` is virtual at vtable offset `0xfc`; native cancel resolves the
active menu's actual handler rather than assuming base `0x00124c20`. Pause Save
activation and cancel changed ownership `0x012e85a0 -> 0x015afa70 ->
`0x012e85a0`. An earlier Press START activation changed ownership
`0x01346590 -> 0x0147d230`, but an identical later saved-state run completed
and restored the call while leaving the source menu active. That Press Start
saved-state transition is not deterministic evidence. All completed deferred calls
attested exact nonzero stack restoration.

The mission-goals load menu is a separate synchronous source. Its singleton is
`0x00367C04` and exact menu vtable is `0x00342570`; while loading, it polls
`GInputDevice` in `GMissionGoalsMenu::LoadHackCallback` before registering the
ordinary callbacks above. `NativeMenuInput` traverses the bounded menu tree and
admits only the unique Exit object with vtable `0x00342370` and CRC
`0xCBC4D4CF`. It invokes that object's exact Focus virtual at `0x00120B70`,
verifies the resulting focus handle resolves back to the same object, and calls
`GMenu::Input(Activate)` synchronously. This call is deliberately not deferred:
the request originates reentrantly while the host-yield observer is at the
modal's loop PC `0x002052C8`, so original guest execution can otherwise revisit
the deferred return PC and falsely report completion. A clean mission run
cleared the singleton and reached the grounded load continuation with exact
stack restoration.

## Menu pointer hit-testing and activation

`GfsPointer::MenuCheck` at `0x0012e490` asks virtual `GetMenuItem` and changes
focus through the returned item. `GfsPointer::GetMenuItem` at `0x0012e8c0`
hit-tests the active `CRender::SelectedList` rectangles and resolves the
matching `GMenuItem`. `GfsPointer::Input_Action` at `0x0012ebb0` activates the
focused item stored at pointer offset `+0x1ac`; `Input_ActionUp` is
`0x0012ec10`. `GMenuPointer` construction at `0x00206540` registers pointer
position/action callbacks, but the live pause pointer is the derived
`GAvPPointer` object at `0x015fe940`, not a concrete `GMenuPointer` instance.

Discovery therefore validates behavior-bearing virtual slots rather than a
single class vtable: GetMenuItem at `+0xd4` resolves to `0x0012e8c0`, absolute
movement at `+0xdc` to `0x0012eab0`, and action at `+0xe0` to `0x0012ebb0`.
This admits the derived gameplay pointer while rejecting unrelated callback
owners. `NativePointerMotion` owns the coordinate, resolution, guest-staging,
and absolute-movement mechanics shared by gameplay and menu semantics.

Absolute position update returns safely through the synchronous EE-call
transaction only on the grounded pause-menu path. `MenuCheck` is deferred
because changing focus can enter game work that depends on the ordinary
scheduler, just as activation does. The windowless pause probe focused Resume
at normalized `(0.7,0.3)`, Save at `(0.7,0.4)`, rejected an out-of-range request
without changing deferred state, and activated Save through the pointer's
original action path. The resulting menu transition was `0x012e85a0 ->
0x015afa70`, with exact deferred stack restoration.

The Save Game menu falsifies extending that direct-call contract. Its complete
`Input_UpdatePositionAbsolute` path leaves the synthetic call through
`SleepThread` (`0x002b3d40`) instead of the interrupted return PC and reaches
the EE BIOS `EENULL` loop (`0x00081fc0`). Its selector mode remains zero, and
the individual `SetPos`, `UpdateWorldPos`, and `StartSelection` calls return,
so neither selector setup nor CInputData stack staging is the cause. Pointer
motion for this yielding menu state must instead enter AVP:E through the normal
`GInputDevice` callback dispatch; `NativePointerMotion` must not extend the
synchronous shuttle contract to cover it.

## Normal input-device dispatch

`GInputDevice::Process` dispatches a callback at `0x001147cc`. At that exact
instruction, `a0` is the resolved callback owner, `a1` is the game-owned
`CInputData` buffer at device `+0xac`, `a2` is the active `CInputDef`, and
`t9` points at the three-word member-function descriptor at callback `+0x0c`.
The following delay slot copies the current input-definition word into that
buffer before `__ptmf_scall`; the callback itself therefore executes on the
ordinary game input/update path rather than a synthetic EE frame.

`NativeInputDispatch` observes that instruction and leaves it unchanged with no
pending event. Schema v2 also records each callback owner's live vtable, which
lets the probe reject a callback whose address survives after its owner changes
class. In the Save Game state it recorded 114 title-admitted dispatches,
all to menu owner `0x015afa70` and direct descriptor `{0, -1, 0x00125230}`
(`GMenu::InputAnalog`) with zero input words. The menu pointer is independently
registered at callback index 0: owner `0x015fe940`, input-definition list
`0x015dd7f4`, and virtual descriptor `{0, 0xd8, 0}`. It did not fire while the
backend was neutral. The diagnostic `POST /input/menu-pointer-dispatch` route
now queues exactly one relative vector, returns its distinct dispatch identity,
waits for its applied coordinates, revalidates the live owner and virtual
descriptor, and replaces only that dispatch's game-owned `CInputData` and
member descriptor. Static decompilation shows that the selected
`GAvPPointer::Input_UpdatePosition` callback calls its `MenuCheck` virtual slot
twice itself: once in the derived routine and once through
`GfsPointer::Input_UpdatePosition`. Therefore it must not queue a third
post-return check. A surfaceless Save Game run injected ticket 1 and moved the
`GPosRot::GetPos` coordinates from `(447.30,178.80)` to `(280.00,378.00)` on
the ordinary callback path. The earlier `(431.33,178.80)` target lay inside a
`GMiner` render rectangle, which `GetMenuItem` correctly rejects. The Save Game
`GMenuButton` rectangle is `(268,366)`–`(292,390)`; its measured center focused
`0x015AFD10`, and the original `GfsPointer::Input_Action` completed through the
ordinary deferred scheduler with exact stack restoration. The product host now
uses this dispatch-bound movement path for every discovered menu; the direct
absolute-motion route remains diagnostic-only. Real-window delivery is still
unobserved.

The visible Save Game slot rows are not a basis for retargeting this control.
`GfsPointer::GetMenuItem` iterates `CRender::SelectedList` from `0x003B40B0`
and admits only handles that dynamically cast to `GMenuItem`. In the saved
state, the measured item is the `GMenuButton` at list entry 21; the visible
first-row entry has a different vtable and does not acquire pointer focus when
its listed rectangle is supplied directly. Thus the rendered 640×480 image is
not a coordinate oracle for this guest hit-test. The measured pointer item
remains a cancellation-path discriminator, not a save-slot selector. The
completed normal game-save probe instead starts from gameplay, waits for the
restored memory card to become available, enters `GSaveGameMenu` through Pause
→ Save, selects a verified empty slot, and uses the descendant
`ActivateFocused` callback above. That path reaches all three
`GSavePacifyMenu::Process` calls and the exact `CProfile::SaveGame` entry and
return; no pointer coordinate is inferred from pixels or retargeted to a slot.

## Native bridge

- `NativePointerMotion::MoveAbsolute` accepts normalized coordinates, validates
  the resolution and caller-supplied pointer, and calls
  `UpdatePositionAbsolute(pointer, {x,y})`. `NativeInput` owns live gameplay
  pointer lookup and absolute selector policy; `NativeMenuInput` owns
  callback-capability discovery and the subsequent hit-test.
- The EE-call shuttle stages the eight-byte `CInputData` in a bounded synthetic
  o32 stack frame, interprets the target call with a distinct jump context,
  restores the interrupted EE/FPU/VU0 context and exact stack bytes, then lets
  the outer scheduler service deferred events. Recursively entering PCSX2's
  recompiler would overwrite its global dispatch jump buffer.
- Non-returning callback-registry menu transitions use the shuttle's deferred
  mode. It reserves a
  guest o32 caller frame, clears the saved return-PC recompiler word, exits the
  current EE block, and completes from the normal interpreter/recompiler
  boundary after AVP:E returns. This keeps IOP, CDVD, timers, and VSync live.
  The synchronous mission-goals load modal is the explicit grounded exception
  described above.
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
S010 mouse evidence is C014 and I005: two pointer coordinates focused distinct
game-owned menu objects, rejected input queued no work, and the focused pointer
action entered a distinct pause submenu with exact deferred restoration.
