"""Bounded invalid-ID diagnostics for AVP:E kernel thread services."""

from __future__ import annotations

import json

from avpe.control_http import request_bytes
from avpe.native_bios_call import BiosCallError, call_signed_v0


DELETE_THREAD = 0x002B3C30
START_THREAD = 0x002B3C40
WAKEUP_THREAD = 0x002B3D50
I_WAKEUP_THREAD = 0x002B3D60
CANCEL_WAKEUP_THREAD = 0x002B3D70
I_CANCEL_WAKEUP_THREAD = 0x002B3D80
INVALID_ID = 0xFFFFFFFF


class ThreadProbeError(RuntimeError):
    """The bounded thread-service negative phase did not establish its contract."""


def probe_thread_invalid_id(port: int, deadline: float) -> dict[str, object]:
    """Capture safe invalid-ID results without creating or waking a thread."""
    status, body = request_bytes(port, "POST", "/bios/trace/start", {})
    if status != 200:
        raise ThreadProbeError(
            f"thread BIOS trace start returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    invalid: dict[str, int] = {}
    for label, function in (
        ("delete_thread", DELETE_THREAD),
        ("start_thread", START_THREAD),
        ("wakeup_thread", WAKEUP_THREAD),
        ("i_wakeup_thread", I_WAKEUP_THREAD),
        ("cancel_wakeup_thread", CANCEL_WAKEUP_THREAD),
        ("i_cancel_wakeup_thread", I_CANCEL_WAKEUP_THREAD),
    ):
        try:
            invalid[label], _ = call_signed_v0(port, deadline, label, function, INVALID_ID)
        except BiosCallError as error:
            raise ThreadProbeError(str(error)) from error
    if any(value != -1 for value in invalid.values()):
        raise ThreadProbeError(f"invalid thread ID results diverged: {invalid}")

    status, body = request_bytes(port, "POST", "/bios/trace/capture", {}, timeout=7.0)
    if status != 200:
        raise ThreadProbeError(
            f"thread BIOS trace capture returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    try:
        trace = json.loads(body)
    except json.JSONDecodeError as error:
        raise ThreadProbeError("thread BIOS trace capture returned malformed JSON") from error
    if not isinstance(trace, dict):
        raise ThreadProbeError("thread BIOS trace capture returned a non-object")
    trace["diagnostic_thread"] = {"invalid_id": invalid}
    return trace


def thread_probe_is_verified(trace: object) -> bool:
    if not isinstance(trace, dict):
        return False
    diagnostic = trace.get("diagnostic_thread")
    if not isinstance(diagnostic, dict):
        return False
    invalid = diagnostic.get("invalid_id")
    if not isinstance(invalid, dict):
        return False
    return all(invalid.get(label) == -1 for label in (
        "delete_thread", "start_thread", "wakeup_thread", "i_wakeup_thread",
        "cancel_wakeup_thread", "i_cancel_wakeup_thread"
    ))
