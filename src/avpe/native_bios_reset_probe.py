"""Bounded BIOS module-release observation around a real guest reset."""

from __future__ import annotations

import json

from avpe.control_http import request_bytes, request_json


class BiosResetCaptureError(RuntimeError):
    """The reset phase did not produce a complete trace."""


def run_guest_reset_phase(port: int) -> tuple[dict[str, object], str, str]:
    """Reset the running guest and require title-owned module release events."""
    status, body = request_bytes(port, "POST", "/bios/trace/start", {})
    if status != 200:
        raise BiosResetCaptureError(
            f"BIOS reset trace start returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    status, response, detail = request_json(port, "POST", "/guest/reset", {})
    if status != 200 or response is None or response.get("reset") is not True:
        raise BiosResetCaptureError(f"guest reset returned HTTP {status}: {detail}")

    status, body = request_bytes(port, "POST", "/bios/trace/capture", {}, timeout=7.0)
    try:
        trace = json.loads(body)
    except json.JSONDecodeError as error:
        raise BiosResetCaptureError("BIOS reset trace returned malformed JSON") from error
    if status != 200 or not isinstance(trace, dict):
        raise BiosResetCaptureError(
            f"BIOS reset trace capture returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    events = trace.get("events")
    if trace.get("schema") != "avpe-bios-trace-v7" \
            or trace.get("enabled") is not True \
            or trace.get("overflow") != 0 \
            or not isinstance(events, list) \
            or not events:
        raise BiosResetCaptureError("BIOS reset trace was incomplete or overflowed")
    releases = [
        event for event in events
        if isinstance(event, dict)
        and event.get("kind") == "module"
        and event.get("operation") == "release"
    ]
    trace["guest_reset"] = {
        "reset": response,
        "release_count": len(releases),
        "release_observed": bool(releases),
        "released_modules": sorted(
            {
                event.get("module")
                for event in releases
                if isinstance(event.get("module"), str)
            }
        ),
        "complete": True,
    }
    return trace, "statefile_to_guest_reset", "guest_reset_module_release"
