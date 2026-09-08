"""Bounded interrupt-controller handler wrapper diagnostics."""

from __future__ import annotations

import json

from avpe.control_http import request_bytes
from avpe.native_bios_call import BiosCallError, call_signed_v0


ENABLE_INTC = 0x002B3FE0
I_ENABLE_INTC = 0x002B3FF0
DISABLE_INTC = 0x002B4000
I_DISABLE_INTC = 0x002B4010
ENABLE_DMAC = 0x002B4020
I_ENABLE_DMAC = 0x002B4030
DISABLE_DMAC = 0x002B4040
I_DISABLE_DMAC = 0x002B4050
INVALID_ID = 0xFFFFFFFF
EXPECTED_RESULTS = {
    "enable_intc": 0xFFFFFFFF,
    "i_enable_intc": 0xFFFFFFFF,
    "disable_intc": 0xFFFFFFFF,
    "i_disable_intc": 0xFFFFFFFF,
    "enable_dmac": 0xFFFFFFFF,
    "i_enable_dmac": 0xFFFFFFFF,
    "disable_dmac": 0xFFFFFFFF,
    "i_disable_dmac": 0xFFFFFFFF,
}


class InterruptHandlerProbeError(RuntimeError):
    """The bounded interrupt-handler wrapper phase failed."""


def probe_interrupt_handler_invalid_id(port: int, deadline: float) -> dict[str, object]:
    status, body = request_bytes(port, "POST", "/bios/trace/start", {})
    if status != 200:
        raise InterruptHandlerProbeError(
            f"interrupt-handler BIOS trace start returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    invalid: dict[str, int] = {}
    for label, function in (
        ("enable_intc", ENABLE_INTC),
        ("i_enable_intc", I_ENABLE_INTC),
        ("disable_intc", DISABLE_INTC),
        ("i_disable_intc", I_DISABLE_INTC),
        ("enable_dmac", ENABLE_DMAC),
        ("i_enable_dmac", I_ENABLE_DMAC),
        ("disable_dmac", DISABLE_DMAC),
        ("i_disable_dmac", I_DISABLE_DMAC),
    ):
        try:
            invalid[label], _ = call_signed_v0(
                port, deadline, label, function, INVALID_ID
            )
        except BiosCallError as error:
            raise InterruptHandlerProbeError(str(error)) from error
    if invalid != EXPECTED_RESULTS:
        raise InterruptHandlerProbeError(
            f"interrupt-handler results diverged: {invalid}"
        )
    status, body = request_bytes(port, "POST", "/bios/trace/capture", {}, timeout=7.0)
    if status != 200:
        raise InterruptHandlerProbeError(
            f"interrupt-handler BIOS trace capture returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    try:
        trace = json.loads(body)
    except json.JSONDecodeError as error:
        raise InterruptHandlerProbeError("interrupt-handler trace returned malformed JSON") from error
    if not isinstance(trace, dict):
        raise InterruptHandlerProbeError("interrupt-handler trace returned a non-object")
    trace["diagnostic_interrupt_handler"] = {"invalid_id": invalid}
    return trace


def interrupt_handler_probe_is_captured(trace: object) -> bool:
    if not isinstance(trace, dict):
        return False
    diagnostic = trace.get("diagnostic_interrupt_handler")
    if not isinstance(diagnostic, dict):
        return False
    invalid = diagnostic.get("invalid_id")
    return invalid == EXPECTED_RESULTS
