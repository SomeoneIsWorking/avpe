# AVPE host presentation boundary

AVPE's product mode owns its visible top-level window in-process. PCSX2 remains
the emulation backend and retains a hidden administrative `MainWindow`, but that
window is not the product presentation surface. The current boundary establishes
one AVPE owner for render-window acquisition and leaves a same-frame composition
seam for RmlUi.

This document distinguishes two evidence levels:

- **Compile-time structure:** implemented in the current source, included in the
  `pcsx2-qt` target, and type-checked by the project's combined C++ build gate.
- **Desktop runtime behavior:** not yet verified. In particular, the current
  structure does not by itself prove that a desktop session maps exactly one
  visible window, presents game frames correctly, handles every dialog, or exits
  cleanly on every supported platform.

## Product selection and ownership

The Python product launcher adds `-avpe-host` to the normal game invocation.
`QtHost::ParseCommandLineOptions()` treats that as a distinct application mode:
it enables batch/no-GUI operation for the generic PCSX2 interface and calls
`AVPE::SetProductHost(true)`.

The process is still one `pcsx2-qt` executable and one Qt application. This is
not a second wrapper process and it does not copy frames through HTTP. During Qt
startup:

1. PCSX2 starts its emulation thread and constructs its normal `MainWindow`.
2. Product mode constructs `AVPE::HostWindow` in the same process.
3. `HostWindow` connects itself to the emulation display signals.
4. Only `HostWindow` is explicitly shown, raised, and activated.
5. The generic `MainWindow` remains unshown because `-avpe-host` also selects
   PCSX2's no-GUI mode.

The relevant owners are:

| Owner | Current location | Responsibility |
|---|---|---|
| Product-mode selection | `thirdparty/pcsx2/pcsx2/AVPE/AVPE.cpp` | Mutually exclusive product-host and surfaceless control-test modes |
| Product top-level window | `thirdparty/pcsx2/pcsx2-qt/AVPE/HostWindow.cpp` | Visible window, render-surface container, fullscreen/resize, focus, cursor mode, close request |
| Emulation display producer | `thirdparty/pcsx2/pcsx2-qt/QtHost.cpp` | Emits render-window lifecycle signals from `EmuThread` |
| Administrative PCSX2 UI | `thirdparty/pcsx2/pcsx2-qt/MainWindow.cpp` | VM administration, legacy dialogs, non-display VM signals, application exit |
| Product launch command | `src/avpe/launch.py` | Invokes the built binary with `-avpe-host` and the product profile |

`MainWindow` is deliberately still constructed. PCSX2 currently uses it as an
administrative controller for VM lifecycle, settings, status signals, shutdown,
and dialogs. Removing it without first extracting those responsibilities would
break internal contracts. Its continued existence is therefore not evidence of
a second product window; its visibility must be checked separately at runtime.

## Render-signal boundary

`EmuThread` remains the producer of PCSX2's existing display lifecycle signals.
Product mode changes only their UI-side owner:

```text
GS / VM requests a host display
            |
            v
EmuThread display signals
            |
            v
AVPE::HostWindow
            |
            +-- creates DisplaySurface
            +-- embeds its native container as the central widget
            +-- connects existing PCSX2 display/input signals
            +-- returns the surface WindowInfo to the GS path
```

The boundary consists of:

- `onAcquireRenderWindowRequested`: a blocking queued connection; creates or
  recreates the AVPE-owned `DisplaySurface`, applies windowed/fullscreen state,
  focuses it, and returns its `WindowInfo`.
- `onReleaseRenderWindowRequested`: a blocking queued connection; detaches and
  retires the current surface.
- `onResizeRenderWindowRequested`: resizes the AVPE top-level window while it is
  windowed.
- `onMouseModeRequested`: applies relative mode and cursor visibility to the
  AVPE-owned surface.
- `onMouseLockRequested`: currently logs the request only; actual pointer-lock
  policy is not implemented.

`MainWindow::connectVMThreadSignals()` skips its five display-related
connections in product mode. This is important: a Qt signal with a return value
must have one authoritative receiver. Connecting both windows would make render
surface acquisition ambiguous and would allow the generic PCSX2 display owner
to create another window.

`Host::GetTopLevelWindowInfo()` also prefers `AVPE::HostWindow` when it exists,
so host facilities which need the native top-level handle do not default to the
hidden administrative window.

The current product host still reuses PCSX2's `DisplaySurface` and its existing
GS presentation path. AVPE owns the top-level window and the surface lifetime;
it does not yet own a separate renderer or frame transport.

## Lifecycle contract and risks

The intended lifecycle is:

```text
parse -avpe-host
  -> start EmuThread
  -> construct hidden administrative MainWindow
  -> construct/show AVPE HostWindow
  -> acquire AVPE render surface
  -> run Qt event loop and VM
  -> request exit from AVPE close event or VM shutdown
  -> stop EmuThread
  -> destroy HostWindow
  -> destroy administrative MainWindow
  -> save settings and exit
```

Closing the product window does not destroy it immediately. `HostWindow` queues
`MainWindow::requestExit(false)`, marks the close request as already forwarded,
and ignores the Qt close event. This preserves PCSX2's existing VM shutdown and
batch-exit path while preventing repeated close requests.

The following lifecycle behavior remains unverified on a desktop:

- a product close request always reaches application exit rather than leaving an
  ignored but visible window behind;
- surface recreation, fullscreen transitions, renderer switches, and VM reset do
  not briefly map the hidden administrative window;
- `deleteLater()` retirement of the surface container cannot race a queued
  resize, cursor, or focus event;
- the host remains the active top-level window after focus loss, pause/resume,
  and renderer recreation;
- shutdown ordering is safe when startup fails before `HostWindow` exists or
  when the VM stops while a dialog is active.

## Input and focus contract

The render surface receives focus after acquisition and continues to use
PCSX2's existing `DisplaySurface` event wiring. Relative mouse mode and cursor
visibility are redirected to that surface. This preserves the existing input
path at compile time, but it does not yet provide the complete PC-native RTS or
RmlUi input policy.

Runtime checks are still required for:

- keyboard and mouse events reaching the game only from the AVPE window;
- absolute pointer coordinates surviving window resize, DPI scaling, and
  fullscreen transitions;
- focus loss clearing held keys/buttons without creating stuck input;
- cursor confinement and relative mode, since mouse-lock requests are currently
  diagnostic only;
- no input being captured by the hidden administrative `MainWindow`.

When RmlUi is added, the host must route each event through the UI first. An
active document consumes the relevant keyboard, mouse, text, or wheel event and
mechanically suppresses the corresponding game action. Unconsumed events then
flow to AVPE's normalized game-input bridge. Menu keyboard/mouse support must not
be implemented by translating native input into a virtual PS2 controller.

## Dialog ownership risk

PCSX2 dialogs have not yet been re-owned. Settings, confirmation, error,
progress, setup, and file-selection paths still assume the administrative
`MainWindow` or another PCSX2 Qt widget is their parent. Because that window is
hidden in product mode, a legacy dialog may:

- appear behind the product window;
- receive an unexpected taskbar entry or focus relationship;
- block the VM while remaining invisible;
- cause the hidden administrative window to become visible during an error or
  shutdown path.

`Host::GetTopLevelWindowInfo()` selecting the AVPE host fixes native-handle
queries, but it does not automatically reparent `QDialog` instances. Product
dialogs need an explicit AVPE-owned dialog service or an RmlUi replacement. Each
remaining legacy dialog call site must either use `HostWindow` as its parent or
be unreachable in the shipping product path. Setup and fatal-startup dialogs
which can occur before `HostWindow` construction need a separate policy rather
than a null or hidden parent.

## Same-frame RmlUi seam

RmlUi must be part of the AVPE presentation path, not a second overlay window or
an external process. The intended frame order is:

```text
acquire AVPE presentation target
  -> render/present the emulated game frame into that target
  -> update the RmlUi context once
  -> render RmlUi into the same target
  -> submit/present once
```

This requires a narrow host-side presentation seam with explicit begin-frame,
game-layer, UI-layer, and end-frame ownership. `Host::BeginPresentFrame()` is
currently empty and is not, by itself, a completed integration point. The final
seam must be placed where both the game image and RmlUi can participate in the
same submitted frame without readback, HTTP transfer, or a second compositor
window.

The RmlUi integration should keep these owners separate:

- a render/system/file backend bound to the AVPE presentation target;
- a UI runtime owning the Rml context, update/render lifetime, documents, and
  focus/capture state;
- individual documents such as graphics, display, audio, and input options;
- typed setting bindings which call existing graphics/input/audio owners rather
  than editing PCSX2 configuration files from UI code.

Resize, DPI, fullscreen, and safe-area changes originate at `HostWindow`, update
the presentation target, and then update the Rml context dimensions before its
next frame. UI shutdown must happen before the render surface and graphics
device are released.

## Evidence boundary

The current compile-time structure establishes:

- an AVPE-specific product mode selected by the real launcher;
- an AVPE-owned top-level `QMainWindow` included in the `pcsx2-qt` target;
- a single product-mode receiver for render-window lifecycle signals;
- a hidden, non-render-owning PCSX2 administrative `MainWindow`;
- host-first top-level native-window lookup;
- an orderly request path from product-window close to PCSX2 VM/application
  shutdown;
- a clear future seam for same-frame RmlUi composition.

It does **not** yet verify:

- exactly one mapped desktop window throughout boot, play, errors, and shutdown;
- correct or continuous frame presentation in the AVPE window;
- keyboard/mouse focus and cursor behavior;
- fullscreen, resize, DPI, and renderer-switch behavior;
- legacy dialog visibility and modality;
- RmlUi rendering, input capture, or options bindings;
- clean desktop shutdown without a hang or transient PCSX2 window.

Those are runtime acceptance gates. They must be proven on the product route,
not inferred from a successful build and not substituted with the surfaceless
control-test path.
