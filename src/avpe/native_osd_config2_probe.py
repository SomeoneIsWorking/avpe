"""Bounded output-buffer diagnostics for the EE GetOsdConfigParam2 wrapper."""

from __future__ import annotations

import json
import time

from avpe.control_http import request_bytes, request_json
from avpe.native_guest_buffer import GuestBufferError, read_guest_buffer, write_guest_buffer


GET_OSD_CONFIG_PARAM2 = 0x002B4130
OUTPUT_ADDRESS = 0x01FF0000
OUTPUT_SIZE = 16
SENTINEL_HEX = "cc" * OUTPUT_SIZE
EXPECTED_PREFIX_HEX = "00000201"
EXPECTED_OUTPUT_HEX = EXPECTED_PREFIX_HEX + ("00" * (OUTPUT_SIZE - 4))


class OsdConfig2ProbeError(RuntimeError):
    """The bounded OSD v2 output-pointer phase did not establish its contract."""


def probe_osd_config2_output(port: int, deadline: float) -> dict[str, object]:
    """Capture the grounded output written by GetOsdConfigParam2."""
    def ensure_deadline(stage: str) -> None:
        if time.monotonic() >= deadline:
            raise OsdConfig2ProbeError(f"OSD v2 output deadline expired before {stage}")

    ensure_deadline("trace start")
    status, body = request_bytes(port, "POST", "/bios/trace/start", {})
    if status != 200:
        raise OsdConfig2ProbeError(
            f"OSD v2 BIOS trace start returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    try:
        write_guest_buffer(port, OUTPUT_ADDRESS, SENTINEL_HEX)
    except GuestBufferError as error:
        raise OsdConfig2ProbeError(str(error)) from error
    ensure_deadline("EE call")
    status, response, detail = request_json(
        port,
        "POST",
        "/ee/call",
        {
            "function": f"0x{GET_OSD_CONFIG_PARAM2:08x}",
            "a0": OUTPUT_ADDRESS,
            "a1": OUTPUT_SIZE,
            "a2": 0,
        },
    )
    if status != 200 or response is None:
        raise OsdConfig2ProbeError(f"GetOsdConfigParam2 returned HTTP {status}: {detail}")
    if response.get("stack_restored") is not True:
        raise OsdConfig2ProbeError("GetOsdConfigParam2 did not restore the guest stack")
    try:
        output_hex = read_guest_buffer(port, OUTPUT_ADDRESS, OUTPUT_SIZE)
    except GuestBufferError as error:
        raise OsdConfig2ProbeError(str(error)) from error
    if output_hex != EXPECTED_OUTPUT_HEX:
        raise OsdConfig2ProbeError(f"OSD v2 output diverged: {output_hex}")

    status, body = request_bytes(port, "POST", "/bios/trace/capture", {}, timeout=7.0)
    if status != 200:
        raise OsdConfig2ProbeError(
            f"OSD v2 BIOS trace capture returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    try:
        trace = json.loads(body)
    except json.JSONDecodeError as error:
        raise OsdConfig2ProbeError("OSD v2 trace returned malformed JSON") from error
    if not isinstance(trace, dict):
        raise OsdConfig2ProbeError("OSD v2 trace returned a non-object")
    trace["diagnostic_osd_config2"] = {
        "address": f"0x{OUTPUT_ADDRESS:08x}",
        "size": OUTPUT_SIZE,
        "offset": 0,
        "seed_hex": SENTINEL_HEX,
        "output_hex": output_hex,
        "written_prefix_hex": EXPECTED_PREFIX_HEX,
    }
    return trace


def osd_config2_probe_is_verified(trace: object) -> bool:
    if not isinstance(trace, dict):
        return False
    diagnostic = trace.get("diagnostic_osd_config2")
    if not isinstance(diagnostic, dict):
        return False
    return (
        diagnostic.get("address") == f"0x{OUTPUT_ADDRESS:08x}"
        and diagnostic.get("size") == OUTPUT_SIZE
        and diagnostic.get("offset") == 0
        and diagnostic.get("seed_hex") == SENTINEL_HEX
        and diagnostic.get("output_hex") == EXPECTED_OUTPUT_HEX
        and diagnostic.get("written_prefix_hex") == EXPECTED_PREFIX_HEX
    )
