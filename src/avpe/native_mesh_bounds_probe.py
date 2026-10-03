"""Synchronous live capture of the AVP:E prompt render dispatch and bounds.

Composes the grounded pause-menu probe with the AVPE::NativeMeshBoundsTrace
diagnostic route entirely within one control-test process, so the arm/poll/
capture sequence never depends on a follow-up HTTP call arriving after the
VM has already shut down. It also captures a same-frame /snap screenshot
between the last observed call and stopping the trace, so the guest-space rects
and the 640x480 screen image can be correlated against the same live geometry
rather than a separate capture/frame.

The live pause-menu object tree supplies the Select/Back items' own image
resources, and those are the only resources the observer is armed with, so a
zero match count means the prompt icon was not drawn through this dispatch
rather than that a bounded table filled up first.
"""

import struct
import time
from pathlib import Path

from avpe.control_http import request_json
from avpe.menu_probe import capture_menu_snapshot
from avpe.native_guest_buffer import read_guest_buffer
from avpe.native_pause_probe import probe_gameplay_pause_menu

# GMenuItem/GMenu layout shared with NativeMenuItems.cpp's ReadMenuDescendants
# and OBJECT_NAME_OFFSET. GMenuItem::Redraw attaches this item's image resource
# to the CRender embedded at GMenuItem+0x70, which is the icon the renderer
# draws for the item.
_FIRST_CHILD_OFFSET = 0x08
_NEXT_SIBLING_OFFSET = 0x10
_OBJECT_NAME_OFFSET = 0x1C
_IMAGE_RESOURCE_OFFSET = 0xF0
_MAIN_SELECT_BUTTON_NAME_HASH = 0x6449F1DE
_MAIN_BACK_BUTTON_NAME_HASH = 0x36D11C7B
_MAX_MENU_OBJECTS = 256


def _guest_word(port: int, address: int) -> int:
    return struct.unpack("<I", bytes.fromhex(read_guest_buffer(port, address, 4)))[0]


def identify_select_back_meshes(port: int, menu_address: int) -> dict[str, dict[str, str]]:
    """Walk the live menu tree and return the Select/Back items' image objects.

    Each image resource is reported with the object's own vtable pointer so a
    captured draw can be identified by which CRend* primitive draws it, not only
    by address.
    """
    pending = [menu_address]
    visited: set[int] = set()
    meshes: dict[str, dict[str, str]] = {}
    while pending and len(visited) < _MAX_MENU_OBJECTS:
        first_child = _guest_word(port, pending.pop() + _FIRST_CHILD_OFFSET)
        node = first_child
        while node != 0 and node not in visited and len(visited) < _MAX_MENU_OBJECTS:
            visited.add(node)
            name_hash = _guest_word(port, node + _OBJECT_NAME_OFFSET)
            if name_hash in (_MAIN_SELECT_BUTTON_NAME_HASH, _MAIN_BACK_BUTTON_NAME_HASH):
                name = "select" if name_hash == _MAIN_SELECT_BUTTON_NAME_HASH else "back"
                resource = _guest_word(port, node + _IMAGE_RESOURCE_OFFSET)
                meshes[name] = {
                    "mesh": f"0x{resource:08X}",
                    "vtable": f"0x{_guest_word(port, resource):08X}",
                }
            pending.append(node)
            node = _guest_word(port, node + _NEXT_SIBLING_OFFSET)
    return meshes


def _correlate(stop_body: dict, select_back_meshes: dict[str, dict[str, str]]) -> dict[str, object]:
    """Match the admitted live observations against the menu items' own resources."""
    wanted = {entry["mesh"].upper(): name for name, entry in select_back_meshes.items()}
    dispatches: dict[str, object] = {}
    rects: dict[str, list[object]] = {}
    for dispatch in stop_body.get("dispatches", []):
        name = wanted.get(str(dispatch.get("resource", "")).upper())
        if name is not None:
            dispatches[name] = dispatch
    for sample in stop_body.get("samples", []):
        name = wanted.get(str(sample.get("bounds_object", "")).upper())
        if name is not None:
            rects.setdefault(name, []).append(sample)
    return {"dispatch": dispatches, "rect": rects}


# Accumulate rects across many frames before capturing, so a moving or animated
# prompt shows up as several distinct rects rather than one.
_MIN_MATCHED_RECTS = 40


def probe_native_mesh_bounds(port: int, deadline: float, output_dir: Path) -> dict[str, object]:
    """Press Start into the pause menu, then arm/capture/stop the render trace."""
    pause = probe_gameplay_pause_menu(port, deadline)

    menu_address_text = pause["menu"].get("menu") if isinstance(pause.get("menu"), dict) else None
    if not isinstance(menu_address_text, str):
        raise RuntimeError(f"pause probe did not report a live menu address: {pause}")
    select_back_meshes = identify_select_back_meshes(port, int(menu_address_text, 16))
    if "select" not in select_back_meshes or "back" not in select_back_meshes:
        raise RuntimeError(
            f"could not identify both Select and Back image resources: {select_back_meshes}"
        )
    resources = [entry["mesh"] for entry in select_back_meshes.values()]

    start_status, start_body, start_detail = request_json(
        port, "POST", "/mesh/bounds-trace", {"resources": resources}
    )
    if start_status != 200 or start_body is None:
        raise RuntimeError(
            f"could not arm the native render trace: HTTP {start_status}: {start_detail}"
        )

    last_snapshot = start_body
    while time.monotonic() < deadline:
        status, snapshot, detail = request_json(port, "GET", "/mesh/bounds-trace", {})
        if status != 200 or snapshot is None:
            raise RuntimeError(f"could not poll the native render trace: HTTP {status}: {detail}")
        last_snapshot = snapshot
        if int(snapshot.get("matched_rects", 0)) >= _MIN_MATCHED_RECTS:
            break
        time.sleep(0.05)

    snapshot_sha256 = capture_menu_snapshot(port, "mesh-bounds-snap.bmp", output_dir)

    stop_status, stop_body, stop_detail = request_json(
        port, "POST", "/mesh/bounds-trace/stop", {}
    )
    if stop_status != 200 or stop_body is None:
        raise RuntimeError(f"could not stop the native render trace: HTTP {stop_status}: {stop_detail}")

    if int(stop_body.get("observed_dispatches", 0)) == 0:
        raise RuntimeError(
            "no CRender draws were observed at all, so the pause menu never reached "
            f"CRender::Display: {select_back_meshes}; last_snapshot={last_snapshot}"
        )

    return {
        "pause_menu": pause,
        "select_back_meshes": select_back_meshes,
        "mesh_bounds": stop_body,
        "select_back_matches": _correlate(stop_body, select_back_meshes),
        "same_frame_snapshot": {
            "path": str(output_dir / "mesh-bounds-snap.bmp"),
            "sha256": snapshot_sha256,
        },
    }