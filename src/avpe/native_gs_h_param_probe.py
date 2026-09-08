"""Bounded output-buffer diagnostics for the EE GetGsHParam wrapper."""

from __future__ import annotations

import json
import time

from avpe.control_http import request_bytes, request_json
from avpe.native_guest_buffer import GuestBufferError, read_guest_buffer, write_guest_buffer


GET_GS_H_PARAM = 0x002B3EE0
BUFFER_ADDRESSES = (0x01FF0000, 0x01FF0010, 0x01FF0020)
BUFFER_SIZE = 16
SENTINEL_HEX = "cc" * BUFFER_SIZE
EXPECTED_PREFIX_HEX = "00000000"


class GsHParamProbeError(RuntimeError):
    """The bounded GS H-parameter output phase did not establish its contract."""


def probe_gs_h_param_output(port: int, deadline: float) -> dict[str, object]:
    """Capture the three grounded four-byte writes made by GetGsHParam."""
    def ensure_deadline(stage: str) -> None:
        if time.monotonic() >= deadline:
            raise GsHParamProbeError(f"GS H-parameter deadline expired before {stage}")

    ensure_deadline("trace start")
    status, body = request_bytes(port, "POST", "/bios/trace/start", {})
    if status != 200:
        raise GsHParamProbeError(
            f"GS H-parameter BIOS trace start returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    try:
        for address in BUFFER_ADDRESSES:
            write_guest_buffer(port, address, SENTINEL_HEX)
    except GuestBufferError as error:
        raise GsHParamProbeError(str(error)) from error
    ensure_deadline("EE call")
    status, response, detail = request_json(
        port,
        "POST",
        "/ee/call",
        {
            "function": f"0x{GET_GS_H_PARAM:08x}",
            "a0": BUFFER_ADDRESSES[0],
            "a1": BUFFER_ADDRESSES[1],
            "a2": BUFFER_ADDRESSES[2],
        },
    )
    if status != 200 or response is None:
        raise GsHParamProbeError(f"GetGsHParam returned HTTP {status}: {detail}")
    if response.get("stack_restored") is not True:
        raise GsHParamProbeError("GetGsHParam did not restore the guest stack")

    expected_hex = EXPECTED_PREFIX_HEX + SENTINEL_HEX[len(EXPECTED_PREFIX_HEX):]
    buffers: list[dict[str, str]] = []
    try:
        for address in BUFFER_ADDRESSES:
            output_hex = read_guest_buffer(port, address, BUFFER_SIZE)
            if output_hex != expected_hex:
                raise GsHParamProbeError(
                    f"GS H-parameter output at 0x{address:08x} diverged: {output_hex}"
                )
            buffers.append({
                "address": f"0x{address:08x}",
                "output_hex": output_hex,
                "written_prefix_hex": EXPECTED_PREFIX_HEX,
            })
    except GuestBufferError as error:
        raise GsHParamProbeError(str(error)) from error

    status, body = request_bytes(port, "POST", "/bios/trace/capture", {}, timeout=7.0)
    if status != 200:
        raise GsHParamProbeError(
            f"GS H-parameter BIOS trace capture returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    try:
        trace = json.loads(body)
    except json.JSONDecodeError as error:
        raise GsHParamProbeError("GS H-parameter trace returned malformed JSON") from error
    if not isinstance(trace, dict):
        raise GsHParamProbeError("GS H-parameter trace returned a non-object")
    trace["diagnostic_gs_h_param"] = {
        "seed_hex": SENTINEL_HEX,
        "buffers": buffers,
        "written_prefix_hex": EXPECTED_PREFIX_HEX,
    }
    return trace


def gs_h_param_probe_is_verified(trace: object) -> bool:
    if not isinstance(trace, dict):
        return False
    diagnostic = trace.get("diagnostic_gs_h_param")
    if not isinstance(diagnostic, dict):
        return False
    expected_hex = EXPECTED_PREFIX_HEX + SENTINEL_HEX[len(EXPECTED_PREFIX_HEX):]
    if diagnostic.get("seed_hex") != SENTINEL_HEX \
            or diagnostic.get("written_prefix_hex") != EXPECTED_PREFIX_HEX:
        return False
    buffers = diagnostic.get("buffers")
    if not isinstance(buffers, list) or len(buffers) != len(BUFFER_ADDRESSES):
        return False
    expected_addresses = [f"0x{address:08x}" for address in BUFFER_ADDRESSES]
    return all(
        isinstance(buffer, dict)
        and buffer.get("address") == address
        and buffer.get("output_hex") == expected_hex
        and buffer.get("written_prefix_hex") == EXPECTED_PREFIX_HEX
        for buffer, address in zip(buffers, expected_addresses)
    )
