# AVPE standalone presentation boundary

The shipping product is `avpe`, a standalone frontend linked to the PCSX2
emulation-core library. It is not a mode of `pcsx2-qt`. The Qt PCSX2 application
remains available only for surfaceless control tests and other oracle work.

## Ownership

| Owner | Responsibility |
|---|---|
| `Main.cpp` | Product CLI and process composition |
| `Settings.*` | Core settings layers and AVPE profile lifetime |
| `EmulationThread.*` | `CPUThreadInitialize`, VM boot/execute/shutdown, CPU-thread dispatch |
| `HostServices.cpp` | PCSX2 `Host` callbacks presented by the AVPE frontend |
| `Runtime.*` | Coordination between the core thread and UI thread |
| `HostWindow.*` | Top-level window, focus, PC input event capture, close request |
| `RenderSurface.*` / `NativeWindow.*` | Low-level native graphics surface and window handles |
| `HostInputRouter.*` | Keyboard and mouse intent translated to native AVP:E actions |

`pcsx2-qt/MainWindow`, `DisplayWidget`, the game list, debugger, dialogs,
settings widgets, and KDDockWidgets are forbidden dependencies of the product
target. `tests/test_structure.py` enforces this boundary from the target
manifest and also rejects restoration of the old `-avpe-host` mode.

## Lifecycle

```text
src/avpe/launch.py
  -> bin/avpe -- GAME
  -> initialize AVPE settings
  -> construct Runtime + HostWindow
  -> start EmulationThread
       -> VMManager::Internal::CPUThreadInitialize
       -> VMManager::Initialize
       -> VMManager::Execute / Reset / Shutdown
  -> PCSX2 GS calls Host::AcquireRenderWindow
       -> Runtime crosses to the UI thread
       -> HostWindow creates RenderSurface
       -> NativeWindow returns WindowInfo
  -> close request sets VMState::Stopping
  -> VM shutdown exits QApplication
```

The product surface is never created by agent verification. The safe product
capability check is `QT_QPA_PLATFORM=offscreen bin/avpe --test-config`, which
initializes settings and exits before constructing `Runtime` or `HostWindow`.
Runtime desktop acceptance remains operator-only through `./run.sh`.

## Native options and diagnostic UI placement

Desktop options extend AVP:E's existing menu system through the fork-local
`AVPE::NativeOptions` owner. That module calls narrow graphics/configuration
interfaces implemented by the standalone frontend; it must not import PCSX2
settings dialogs or make `HostWindow` own option policy. Keyboard and mouse
support enters through the same typed input boundary used by all game menus.

RmlUi may provide a developer-only diagnostic overlay under `DebugUI/`. It can
inspect the same narrow host interfaces, but it does not own shipping settings
presentation or persistence.
