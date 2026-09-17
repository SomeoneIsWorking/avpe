"""Synchronous live capture of the native HUD mesh screen-bounds observer.

Composes the grounded pause-menu probe with the AVPE::NativeMeshBoundsTrace
diagnostic route entirely within one control-test process, so the arm/poll/
capture sequence never depends on a follow-up HTTP call arriving after the
VM has already shut down. It also captures a same-frame /snap screenshot
between the last observed call and stopping the trace, so the guest-space
rects and the 640x480 screen image can be correlated against the same live
geometry rather than a separate capture/frame.
"""

import time
from pathlib import Path

from avpe.control_http import request_json
from avpe.menu_probe import capture_menu_snapshot
from avpe.native_pause_probe import probe_gameplay_pause_menu


def probe_native_mesh_bounds(port: int, deadline: float, output_dir: Path) -> dict[str, object]:
    """Press Start into the pause menu, then arm/capture/stop the mesh-bounds trace."""
    pause = probe_gameplay_pause_menu(port, deadline)

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
        "mesh_bounds": stop_body,
        "same_frame_snapshot": {
            "path": str(output_dir / "mesh-bounds-snap.bmp"),
            "sha256": snapshot_sha256,
        },
    }
