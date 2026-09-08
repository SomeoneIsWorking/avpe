"""Bounded AVP:E SIF-register query diagnostics."""

from __future__ import annotations

import json

from avpe.control_http import request_bytes
from avpe.native_bios_call import BiosCallError, call_signed_v0


SIF_GET_REG = 0x002B4230
EXPECTED_REGISTERS = {
    "selector_0": 0x0000000000000000,
    "selector_1": 0x0000000000000000,
    "selector_2": 0x000000000001D1E0,
    "selector_3": 0x0000000000010000,
    "selector_4": 0x0000000000070000,
}


class SifQueryProbeError(RuntimeError):
    """The bounded SIF-register query phase did not establish its contract."""


def probe_sif_registers(port: int, deadline: float) -> dict[str, object]:
    """Capture grounded SIF-register values from a restored AVP:E state."""
    status, body = request_bytes(port, "POST", "/bios/trace/start", {})
    if status != 200:
        raise SifQueryProbeError(
            f"SIF-query BIOS trace start returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    registers: dict[str, int] = {}
    for selector in range(5):
        label = f"selector_{selector}"
        try:
            value, _response = call_signed_v0(
                port, deadline, label, SIF_GET_REG, selector
            )
        except BiosCallError as error:
            raise SifQueryProbeError(str(error)) from error
        registers[label] = value
    if registers != EXPECTED_REGISTERS:
        raise SifQueryProbeError(f"SIF-register results diverged: {registers}")

    status, body = request_bytes(port, "POST", "/bios/trace/capture", {}, timeout=7.0)
    if status != 200:
        raise SifQueryProbeError(
            f"SIF-query BIOS trace capture returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    try:
        trace = json.loads(body)
    except json.JSONDecodeError as error:
        raise SifQueryProbeError("SIF-query trace returned malformed JSON") from error
    if not isinstance(trace, dict):
        raise SifQueryProbeError("SIF-query trace returned a non-object")
    trace["diagnostic_sif_query"] = {"registers": registers}
    return trace


def sif_query_probe_is_verified(trace: object) -> bool:
    if not isinstance(trace, dict):
        return False
    diagnostic = trace.get("diagnostic_sif_query")
    return isinstance(diagnostic, dict) \
        and diagnostic.get("registers") == EXPECTED_REGISTERS
