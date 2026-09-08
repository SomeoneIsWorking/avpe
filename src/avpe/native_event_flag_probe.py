"""Bounded invalid-ID diagnostics for AVP:E event-flag services."""

from __future__ import annotations

import json

from avpe.control_http import request_bytes
from avpe.native_bios_call import BiosCallError, call_signed_v0


DELETE_EVENT_FLAG = 0x002B3F30
SET_EVENT_FLAG = 0x002B3F40
I_SET_EVENT_FLAG = 0x002B3F50
POLL_EVENT_FLAG = 0x002B3F90
I_POLL_EVENT_FLAG = 0x002B3FA0
REFER_EVENT_FLAG = 0x002B3FB0
I_REFER_EVENT_FLAG = 0x002B3FC0
INVALID_ID = 0xFFFFFFFF
EXPECTED_RESULTS = {
    "delete_event_flag": 10,
    "set_event_flag": 0,
    "i_set_event_flag": 1,
    "poll_event_flag": -1,
    "i_poll_event_flag": -1,
    "refer_event_flag": -1,
    "i_refer_event_flag": 0,
}


class EventFlagProbeError(RuntimeError):
    """The bounded event-flag invalid-ID phase did not establish its contract."""


def probe_event_flag_invalid_id(port: int, deadline: float) -> dict[str, object]:
    """Capture nonblocking invalid-ID results without creating a flag or waiter."""
    status, body = request_bytes(port, "POST", "/bios/trace/start", {})
    if status != 200:
        raise EventFlagProbeError(
            f"event-flag BIOS trace start returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    invalid: dict[str, int] = {}
    for label, function in (
        ("delete_event_flag", DELETE_EVENT_FLAG),
        ("set_event_flag", SET_EVENT_FLAG),
        ("i_set_event_flag", I_SET_EVENT_FLAG),
        ("poll_event_flag", POLL_EVENT_FLAG),
        ("i_poll_event_flag", I_POLL_EVENT_FLAG),
        ("refer_event_flag", REFER_EVENT_FLAG),
        ("i_refer_event_flag", I_REFER_EVENT_FLAG),
    ):
        try:
            invalid[label], _ = call_signed_v0(
                port, deadline, label, function, INVALID_ID
            )
        except BiosCallError as error:
            raise EventFlagProbeError(str(error)) from error
    if invalid != EXPECTED_RESULTS:
        raise EventFlagProbeError(f"invalid event-flag ID results diverged: {invalid}")

    status, body = request_bytes(port, "POST", "/bios/trace/capture", {}, timeout=7.0)
    if status != 200:
        raise EventFlagProbeError(
            f"event-flag BIOS trace capture returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    try:
        trace = json.loads(body)
    except json.JSONDecodeError as error:
        raise EventFlagProbeError("event-flag BIOS trace capture returned malformed JSON") from error
    if not isinstance(trace, dict):
        raise EventFlagProbeError("event-flag BIOS trace capture returned a non-object")
    trace["diagnostic_event_flag"] = {"invalid_id": invalid}
    return trace


def event_flag_probe_is_verified(trace: object) -> bool:
    if not isinstance(trace, dict):
        return False
    diagnostic = trace.get("diagnostic_event_flag")
    if not isinstance(diagnostic, dict):
        return False
    invalid = diagnostic.get("invalid_id")
    if not isinstance(invalid, dict):
        return False
    return invalid == EXPECTED_RESULTS
