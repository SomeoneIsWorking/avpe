"""Bounded invalid-token diagnostics for the EE GetEntryAddress wrapper."""

from __future__ import annotations

import json

from avpe.control_http import request_bytes
from avpe.native_bios_call import BiosCallError, call_signed_v0


GET_ENTRY_ADDRESS = 0x002B3FD0
INVALID_ENTRY_TOKEN = 0xFFFFFFFF
EXPECTED_RESULT = 0


class EntryAddressProbeError(RuntimeError):
    """The bounded invalid-entry-address phase did not establish its contract."""


def probe_invalid_entry_address(port: int, deadline: float) -> dict[str, object]:
    """Capture the grounded invalid-token result without creating loader state."""
    status, body = request_bytes(port, "POST", "/bios/trace/start", {})
    if status != 200:
        raise EntryAddressProbeError(
            f"entry-address BIOS trace start returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    try:
        result, _response = call_signed_v0(
            port, deadline, "invalid_entry_token", GET_ENTRY_ADDRESS, INVALID_ENTRY_TOKEN
        )
    except BiosCallError as error:
        raise EntryAddressProbeError(str(error)) from error
    if result != EXPECTED_RESULT:
        raise EntryAddressProbeError(f"invalid entry-address result diverged: {result}")

    status, body = request_bytes(port, "POST", "/bios/trace/capture", {}, timeout=7.0)
    if status != 200:
        raise EntryAddressProbeError(
            f"entry-address BIOS trace capture returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    try:
        trace = json.loads(body)
    except json.JSONDecodeError as error:
        raise EntryAddressProbeError("entry-address trace returned malformed JSON") from error
    if not isinstance(trace, dict):
        raise EntryAddressProbeError("entry-address trace returned a non-object")
    trace["diagnostic_entry_address"] = {
        "token": f"0x{INVALID_ENTRY_TOKEN:08x}",
        "result": result,
    }
    return trace


def entry_address_probe_is_verified(trace: object) -> bool:
    if not isinstance(trace, dict):
        return False
    diagnostic = trace.get("diagnostic_entry_address")
    return isinstance(diagnostic, dict) \
        and diagnostic.get("token") == "0xffffffff" \
        and diagnostic.get("result") == EXPECTED_RESULT
