"""Bounded invalid-ID diagnostics for AVP:E kernel alarm services."""

from __future__ import annotations

import json

from avpe.control_http import request_bytes
from avpe.native_bios_call import BiosCallError, call_signed_v0


RELEASE_ALARM = 0x002B3BF0
I_RELEASE_ALARM = 0x002B3C10
INVALID_ID = 0xFFFFFFFF
EXPECTED_RESULTS = {
    "release_alarm": 0,
    "i_release_alarm": -1,
}


class AlarmProbeError(RuntimeError):
    """The bounded alarm-service negative phase did not establish its contract."""


def probe_alarm_invalid_id(port: int, deadline: float) -> dict[str, object]:
    """Capture invalid-ID results without creating or scheduling an alarm."""
    status, body = request_bytes(port, "POST", "/bios/trace/start", {})
    if status != 200:
        raise AlarmProbeError(
            f"alarm BIOS trace start returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    invalid: dict[str, int] = {}
    for label, function in (
        ("release_alarm", RELEASE_ALARM),
        ("i_release_alarm", I_RELEASE_ALARM),
    ):
        try:
            invalid[label], _ = call_signed_v0(port, deadline, label, function, INVALID_ID)
        except BiosCallError as error:
            raise AlarmProbeError(str(error)) from error
    if invalid != EXPECTED_RESULTS:
        raise AlarmProbeError(f"invalid alarm ID results diverged: {invalid}")

    status, body = request_bytes(port, "POST", "/bios/trace/capture", {}, timeout=7.0)
    if status != 200:
        raise AlarmProbeError(
            f"alarm BIOS trace capture returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    try:
        trace = json.loads(body)
    except json.JSONDecodeError as error:
        raise AlarmProbeError("alarm BIOS trace capture returned malformed JSON") from error
    if not isinstance(trace, dict):
        raise AlarmProbeError("alarm BIOS trace capture returned a non-object")
    trace["diagnostic_alarm"] = {"invalid_id": invalid}
    return trace


def alarm_probe_is_verified(trace: object) -> bool:
    if not isinstance(trace, dict):
        return False
    diagnostic = trace.get("diagnostic_alarm")
    return isinstance(diagnostic, dict) and diagnostic.get("invalid_id") == EXPECTED_RESULTS
