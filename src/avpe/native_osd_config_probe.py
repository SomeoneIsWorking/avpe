"""Bounded output-buffer diagnostics for the EE GetOsdConfigParam wrapper."""

from __future__ import annotations

import json
import time

from avpe.control_http import request_bytes, request_json


GET_OSD_CONFIG_PARAM = 0x002B3ED0
OUTPUT_ADDRESS = 0x01FF0000
OUTPUT_SIZE = 32
SENTINEL_HEX = "cc" * OUTPUT_SIZE
EXPECTED_PREFIX_HEX = "102081da"


class OsdConfigProbeError(RuntimeError):
    """The bounded OSD output-pointer phase did not establish its contract."""


def _read_output(port: int) -> str:
    status, body = request_bytes(
        port, "GET", "/mem/read?addr=0x01ff0000&len=0x20", timeout=3.0
    )
    if status != 200:
        raise OsdConfigProbeError(
            f"OSD output read returned HTTP {status}: {body.decode(errors='replace').strip()}"
        )
    try:
        response = json.loads(body)
    except json.JSONDecodeError as error:
        raise OsdConfigProbeError("OSD output read returned malformed JSON") from error
    if not isinstance(response, dict) or not isinstance(response.get("hex"), str):
        raise OsdConfigProbeError("OSD output read omitted its hex buffer")
    return response["hex"]


def probe_osd_config_output(port: int, deadline: float) -> dict[str, object]:
    """Capture the grounded four-byte output written by GetOsdConfigParam."""
    def ensure_deadline(stage: str) -> None:
        if time.monotonic() >= deadline:
            raise OsdConfigProbeError(f"OSD output deadline expired before {stage}")

    ensure_deadline("trace start")
    status, body = request_bytes(port, "POST", "/bios/trace/start", {})
    if status != 200:
        raise OsdConfigProbeError(
            f"OSD BIOS trace start returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    status, _response, detail = request_json(
        port, "POST", "/mem/write", {"addr": "0x01ff0000", "hex": SENTINEL_HEX}
    )
    if status != 200:
        raise OsdConfigProbeError(f"OSD output seed returned HTTP {status}: {detail}")
    ensure_deadline("EE call")
    status, response, detail = request_json(
        port, "POST", "/ee/call", {"function": f"0x{GET_OSD_CONFIG_PARAM:08x}", "a0": OUTPUT_ADDRESS}
    )
    if status != 200 or response is None:
        raise OsdConfigProbeError(f"GetOsdConfigParam returned HTTP {status}: {detail}")
    if response.get("stack_restored") is not True:
        raise OsdConfigProbeError("GetOsdConfigParam did not restore the guest stack")
    output_hex = _read_output(port)
    expected_hex = EXPECTED_PREFIX_HEX + SENTINEL_HEX[len(EXPECTED_PREFIX_HEX):]
    if output_hex != expected_hex:
        raise OsdConfigProbeError(f"OSD output diverged: {output_hex}")

    status, body = request_bytes(port, "POST", "/bios/trace/capture", {}, timeout=7.0)
    if status != 200:
        raise OsdConfigProbeError(
            f"OSD BIOS trace capture returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    try:
        trace = json.loads(body)
    except json.JSONDecodeError as error:
        raise OsdConfigProbeError("OSD trace returned malformed JSON") from error
    if not isinstance(trace, dict):
        raise OsdConfigProbeError("OSD trace returned a non-object")
    trace["diagnostic_osd_config"] = {
        "address": f"0x{OUTPUT_ADDRESS:08x}",
        "seed_hex": SENTINEL_HEX,
        "output_hex": output_hex,
        "written_prefix_hex": EXPECTED_PREFIX_HEX,
    }
    return trace


def osd_config_probe_is_verified(trace: object) -> bool:
    if not isinstance(trace, dict):
        return False
    diagnostic = trace.get("diagnostic_osd_config")
    if not isinstance(diagnostic, dict):
        return False
    expected_hex = EXPECTED_PREFIX_HEX + SENTINEL_HEX[len(EXPECTED_PREFIX_HEX):]
    return diagnostic.get("address") == "0x01ff0000" \
        and diagnostic.get("seed_hex") == SENTINEL_HEX \
        and diagnostic.get("output_hex") == expected_hex \
        and diagnostic.get("written_prefix_hex") == EXPECTED_PREFIX_HEX
