"""Synchronous live capture of the native HUD mesh screen-bounds observer.

Composes the grounded pause-menu probe with the AVPE::NativeMeshBoundsTrace
diagnostic route entirely within one control-test process, so the arm/poll/
capture sequence never depends on a follow-up HTTP call arriving after the
VM has already shut down. It also captures a same-frame /snap screenshot
between the last observed call and stopping the trace, so the guest-space
rects and the 640x480 screen image can be correlated against the same live
geometry rather than a separate capture/frame. It additionally walks the
live pause-menu object tree to identify the Select/Back items' own
CRendPS2Mesh resource addresses, so the captured trace samples can be
matched by identity instead of by guessing a coordinate transform.
"""

import struct
import time
from pathlib import Path

from avpe.control_http import request_json
from avpe.menu_probe import capture_menu_snapshot
from avpe.native_guest_buffer import read_guest_buffer
from avpe.native_pause_probe import probe_gameplay_pause_menu

# GMenuItem/GMenu layout shared with NativeMenuItems.cpp's ReadMenuDescendants
# and OBJECT_NAME_OFFSET; the image resource offset is grounded by issue #8's
# 2026-09-12 "live profile Select item" finding (GMenuItem::Redraw's +0xF0).
_FIRST_CHILD_OFFSET = 0x08
_NEXT_SIBLING_OFFSET = 0x10
_OBJECT_NAME_OFFSET = 0x1C
_IMAGE_RESOURCE_OFFSET = 0xF0
_MAIN_SELECT_BUTTON_NAME_HASH = 0x6449F1DE
_MAIN_BACK_BUTTON_NAME_HASH = 0x36D11C7B
_MAX_MENU_OBJECTS = 256


def _guest_word(port: int, address: int) -> int:
    return struct.unpack("<I", bytes.fromhex(read_guest_buffer(port, address, 4)))[0]


def identify_select_back_meshes(port: int, menu_address: int) -> dict[str, str]:
    """Walk the live menu tree and return the Select/Back items' image mesh addresses."""
    pending = [menu_address]
    visited: set[int] = set()
    meshes: dict[str, str] = {}
    while pending and len(visited) < _MAX_MENU_OBJECTS:
        first_child = _guest_word(port, pending.pop() + _FIRST_CHILD_OFFSET)
        node = first_child
        while node != 0 and node not in visited and len(visited) < _MAX_MENU_OBJECTS:
            visited.add(node)
            name_hash = _guest_word(port, node + _OBJECT_NAME_OFFSET)
            if name_hash == _MAIN_SELECT_BUTTON_NAME_HASH:
                meshes["select_mesh"] = f"0x{_guest_word(port, node + _IMAGE_RESOURCE_OFFSET):08X}"
            elif name_hash == _MAIN_BACK_BUTTON_NAME_HASH:
                meshes["back_mesh"] = f"0x{_guest_word(port, node + _IMAGE_RESOURCE_OFFSET):08X}"
            pending.append(node)
            node = _guest_word(port, node + _NEXT_SIBLING_OFFSET)
    return meshes


def probe_native_mesh_bounds(port: int, deadline: float, output_dir: Path) -> dict[str, object]:
    """Press Start into the pause menu, then arm/capture/stop the mesh-bounds trace."""
    pause = probe_gameplay_pause_menu(port, deadline)

    menu_address_text = pause["menu"].get("menu") if isinstance(pause.get("menu"), dict) else None
    if not isinstance(menu_address_text, str):
        raise RuntimeError(f"pause probe did not report a live menu address: {pause}")
    select_back_meshes = identify_select_back_meshes(port, int(menu_address_text, 16))
    if "select_mesh" not in select_back_meshes or "back_mesh" not in select_back_meshes:
        raise RuntimeError(
            f"could not identify both Select and Back mesh resources: {select_back_meshes}"
        )

    start_status, start_body, start_detail = request_json(port, "POST", "/mesh/bounds-trace", {})
    if start_status != 200 or start_body is None:
        raise RuntimeError(
            f"could not arm the native mesh-bounds trace: HTTP {start_status}: {start_detail}"
        )

    last_snapshot = start_body
    while time.monotonic() < deadline:
        status, snapshot, detail = request_json(port, "GET", "/mesh/bounds-trace", {})
        if status != 200 or snapshot is None:
            raise RuntimeError(
                f"could not poll the native mesh-bounds trace: HTTP {status}: {detail}"
            )
        last_snapshot = snapshot
        if int(snapshot.get("observed_calls", 0)) > 0:
            break
        time.sleep(0.05)

    snapshot_sha256 = capture_menu_snapshot(port, "mesh-bounds-snap.bmp", output_dir)

    stop_status, stop_body, stop_detail = request_json(
        port, "POST", "/mesh/bounds-trace/stop", {}
    )
    if stop_status != 200 or stop_body is None:
        raise RuntimeError(
            f"could not stop the native mesh-bounds trace: HTTP {stop_status}: {stop_detail}"
        )

    if int(stop_body.get("observed_calls", 0)) == 0:
        raise RuntimeError(
            "native mesh-bounds trace observed no calls before the probe deadline: "
            f"last_snapshot={last_snapshot}"
        )

    return {
        "pause_menu": pause,
        "select_back_meshes": select_back_meshes,
        "mesh_bounds": stop_body,
        "same_frame_snapshot": {
            "path": str(output_dir / "mesh-bounds-snap.bmp"),
            "sha256": snapshot_sha256,
        },
    }
