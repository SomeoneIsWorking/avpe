"""Bounded invalid-ID diagnostics for AVP:E kernel thread services."""

from __future__ import annotations

import json

from avpe.control_http import request_bytes
from avpe.native_bios_call import BiosCallError, call_signed_v0


DELETE_THREAD = 0x002B3C30
START_THREAD = 0x002B3C40
REFER_THREAD_STATUS = 0x002B3D20
I_REFER_THREAD_STATUS = 0x002B3D30
RELEASE_WAIT_THREAD = 0x002B3CF0
I_RELEASE_WAIT_THREAD = 0x002B3D00
WAKEUP_THREAD = 0x002B3D50
I_WAKEUP_THREAD = 0x002B3D60
CANCEL_WAKEUP_THREAD = 0x002B3D70
I_CANCEL_WAKEUP_THREAD = 0x002B3D80
SUSPEND_THREAD = 0x002B3D90
I_SUSPEND_THREAD = 0x002B3DA0
RESUME_THREAD = 0x002B3DB0
I_RESUME_THREAD = 0x002B3DC0
JOIN_THREAD = 0x002B3DD0
INVALID_ID = 0xFFFFFFFF
EXPECTED_RESULTS = {
    "delete_thread": -1,
    "start_thread": -1,
    "refer_thread_status": -1,
    "i_refer_thread_status": -1,
    "release_wait_thread": -1,
    "i_release_wait_thread": -1,
    "wakeup_thread": -1,
    "i_wakeup_thread": -1,
    "cancel_wakeup_thread": -1,
    "i_cancel_wakeup_thread": -1,
}
CONTROL_EXPECTED_RESULTS = {
    "suspend_thread": -1,
    "i_suspend_thread": -1,
    "resume_thread": -1,
    "i_resume_thread": -1,
    "join_thread": 0,
}


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
        ("refer_thread_status", REFER_THREAD_STATUS),
        ("i_refer_thread_status", I_REFER_THREAD_STATUS),
        ("release_wait_thread", RELEASE_WAIT_THREAD),
        ("i_release_wait_thread", I_RELEASE_WAIT_THREAD),
        ("wakeup_thread", WAKEUP_THREAD),
        ("i_wakeup_thread", I_WAKEUP_THREAD),
        ("cancel_wakeup_thread", CANCEL_WAKEUP_THREAD),
        ("i_cancel_wakeup_thread", I_CANCEL_WAKEUP_THREAD),
    ):
        try:
            invalid[label], _ = call_signed_v0(port, deadline, label, function, INVALID_ID)
        except BiosCallError as error:
            raise ThreadProbeError(str(error)) from error
    if invalid != EXPECTED_RESULTS:
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
    return invalid == EXPECTED_RESULTS


def probe_thread_control_invalid_id(port: int, deadline: float) -> dict[str, object]:
    """Capture nonblocking invalid-ID suspend/resume/join result shapes."""
    status, body = request_bytes(port, "POST", "/bios/trace/start", {})
    if status != 200:
        raise ThreadProbeError(
            f"thread-control BIOS trace start returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    results: dict[str, int] = {}
    for label, function in (
        ("suspend_thread", SUSPEND_THREAD),
        ("i_suspend_thread", I_SUSPEND_THREAD),
        ("resume_thread", RESUME_THREAD),
        ("i_resume_thread", I_RESUME_THREAD),
        ("join_thread", JOIN_THREAD),
    ):
        try:
            results[label], _ = call_signed_v0(port, deadline, label, function, INVALID_ID)
        except BiosCallError as error:
            raise ThreadProbeError(str(error)) from error
    if results != CONTROL_EXPECTED_RESULTS:
        raise ThreadProbeError(f"thread-control results diverged: {results}")

    status, body = request_bytes(port, "POST", "/bios/trace/capture", {}, timeout=7.0)
    if status != 200:
        raise ThreadProbeError(
            f"thread-control BIOS trace capture returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    try:
        trace = json.loads(body)
    except json.JSONDecodeError as error:
        raise ThreadProbeError("thread-control trace returned malformed JSON") from error
    if not isinstance(trace, dict):
        raise ThreadProbeError("thread-control trace returned a non-object")
    trace["diagnostic_thread_control"] = {"invalid_id": results}
    return trace


def thread_control_probe_is_verified(trace: object) -> bool:
    if not isinstance(trace, dict):
        return False
    diagnostic = trace.get("diagnostic_thread_control")
    if not isinstance(diagnostic, dict):
        return False
    return diagnostic.get("invalid_id") == CONTROL_EXPECTED_RESULTS
