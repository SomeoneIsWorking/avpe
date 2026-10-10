# 0021 Mission controls as a PC RTS

Goal: in a mission, mouse and keyboard work as in a PC RTS (StarCraft): click and drag-box
selection, double-click and Ctrl+click select a unit type, Shift+click adds or removes, right
click issues the context order, the cursor at the screen edge scrolls, the minimap jumps the
camera, Esc or Enter skips cinematics, and the command card is visible and clickable.

## Pointer model

`GAvPPointer` (`pThe` `0x00367720`) has three input types at `+0x224`: 0 and 2 are the pad and
relative paths, 1 is the absolute path the port drives (`SetInputType(1)`,
`GfsPointer::Input_UpdatePositionAbsolute` `0x0012EAB0`).

- Left press (`Input_PressMouse1` `0x001B52C0`) calls `SelectChanging(true)`: `ResetPointer`
  sets the grow flag `+0x1B8` and, in type 1, unregisters the camera's input until release.
- While the flag is set, `UpdateGrowBox` (`0x001B44B0`, last call of `GAvPPointer::Process`)
  grows the box corners `+0x188` (min x, y) and `+0x194` (max x, y) every frame around the press
  point and links its disk render (`+0x10C`) once it is 25 pixels wide.
- Left release calls `SelectChanging(false)`: the corners are clipped and the vt `+0x100`
  selection runs over them. A release within 0.5 s of the previous one calls
  `DoubleClickSelectChanging` (`0x001B2790`): every on-screen unit of the first selected unit's
  UI class is selected.
- Types 0 and 2 only: `Input_UpdatePosition` (`0x001B51A0`) writes the pointer into `+0x194`
  (the box follows the cursor) and calls `CheckBorderPan` (`0x001B4740`), which moves the camera
  when the pointer is in the outer eighth of the screen.
- Right release (`Input_ReleaseMouse2` `0x001B5310`) calls `CommandMove`.
- The pad's context button is Circle (`GInputDevice` input 7 on device 4). While units are
  selected the game registers one DWIM button for what the cursor is over: `GDwimMenuButton`
  (vt `0x0035B9A0`; attack, pick up, enter, ...) or, over ground, `GMoveDwimMenuButton` (vt
  `0x0035B8A0`). Press runs its focus key, release its hotkey (`GMenuItem` `0x00120F90`/
  `0x00120F40`; move `0x0027C530`/`0x0027C3A0`, which also rotate the formation while held).
- These callbacks, and `SelectChanging`'s `PlaySound`, wait on SIF: a synchronous shuttle call
  can spin in `sceSifCheckStatRpc` (`0x002B71A0`) until its cycle budget runs out, because IOP
  events are deferred during the call (17 of 60 synchronous left clicks overran, and the faulted
  shuttle then refuses all native input until a state load). They run on the deferred shuttle,
  through the ordinary scheduler. Injecting them as `GInputDevice` callbacks does not work: the
  guest dispatches only when some callback's input fires, which an idle mission rarely does.
- `GfsPointer::Select` (`0x0012DC30`) takes every object whose screen bounds overlap the box;
  a box of 15 pixels or less takes the object nearest its centre.

## Gaps (M1, `scratch/prompt-probe/mission-normal-current.p2s`)

| PC RTS behaviour | observed |
|---|---|
| drag a rectangle from press to cursor | fixed: `NativeDragSelect` pins the corners to the press point and cursor after each `UpdateGrowBox`; holding still on empty ground selects nothing; the guest still draws its circle inside the box |
| click selects the unit under it | yes |
| double-click selects the type | fixed: `HostPointerInput` passes a mission double-click as a second click (unit-tested; the guest times it) |
| Ctrl+click / Shift+click | fixed: `NativeMouseButtons::Calls` runs the guest's own sequences: Shift is `SelectChanging(p, false, true)` (`0x001B26A0`), so `GfsPointer::Select` adds the box and toggles a clicked unit; Ctrl adds `DoubleClickSelectChanging` (`0x001B2790`); both end with `GInGameMenu::Refresh` (`0x00279670`) as `Input_ReleaseMouse1` does; live: 1, Shift 2, Shift 3, Shift on a selected unit 2, Ctrl on infantry 5 |
| cursor at the screen edge scrolls | fixed: `HostPointerInput` scrolls the camera at arrow-key speed while the cursor is within 2% of an image edge or in a letterbox bar, and stops when it leaves the window (unit-tested) |
| arrows scroll, wheel zooms | yes (camera input is unregistered while the left button is held) |
| Esc or Enter skips the intro | fixed: with no menu open, `NativeMenuInput` calls the `GSkipLevelIntro` button's registered `GMenuItem::HotKeyActivate` synchronously (the guest dispatches input only on pad events); its `Process` stops the intro and destroys the button; checked live from `scratch/prompt-probe/mission-current.p2s` |
| inline prompt text ("Press ✕ to Skip Intro") | PS2 glyph |
| right click on an enemy attacks | fixed: `NativeMouseButtons` runs the registered DWIM button's focus key on press and hotkey on release, as Circle does, on the deferred shuttle; live from `scratch/rts-audit/contact.p2s` (five marines next to drones): an enemy gives attack `0x60030`, ground moves the squad |
| minimap click jumps the camera | fixed: a left press or drag on the map calls `GAvPCamera::Move` (`0x001AF660`) with the world point under the pointer (`GMiniMap::GetCamPointerPos` mapping in `NativeMinimap`) and is not passed to selection; checked live at map centre (target 113, 113) and corner (9, 7) |
| command card always visible and clickable | no: shown only while Tab (R2) is held |
| buy units from a clickable production panel | no: the Comm Tech's Dropship Uplink (`GOrderingMenu`, vt `0x0033C720`) opens only through Q (R1 special) with one Comm Tech selected, and is navigated as the PS2 menu with key caps (Order O, Clear C, Select S, Exit E); units are not clickable and there is no always-available build hotkey |
| clicks never stall the shuttle | fixed: every mouse edge's calls run in order on the deferred shuttle; live: 180 mixed plain, Shift and Ctrl clicks with no overrun or refusal after one run of 60 with 36 refused edges that did not recur |

## Resolution

Open.
