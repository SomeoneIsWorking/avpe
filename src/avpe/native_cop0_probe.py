"""Bounded read-only COP0 register diagnostics for the EE BIOS inventory."""

from __future__ import annotations

import json

from avpe.control_http import request_bytes
from avpe.native_bios_call import BiosCallError, call_signed_v0


GET_COP0 = 0x002B4090
# These registers were stable across two restored-state runs. Volatile timing
# and exception registers remain outside this snapshot phase.
EXPECTED_REGISTERS = {
    0: 0x00000026,
    1: 0x00000000,
    2: 0x0006003F,
    3: 0x0007003F,
    4: 0x00000000,
    8: 0x00000000,
    10: 0x3180003E,
    11: 0x00000001,
    12: 0x70030C00,
    15: 0x00002E20,
    16: 0x00073443,
    25: 0x00000000,
    28: 0x00000000,
    29: 0x00000000,
    30: 0x00000000,
    31: 0x00000000,
}


class Cop0ProbeError(RuntimeError):
    """The bounded COP0 query phase did not establish its contract."""


def probe_cop0_registers(port: int, deadline: float) -> dict[str, object]:
    """Capture stable read-only COP0 register values from a restored state."""
    status, body = request_bytes(port, "POST", "/bios/trace/start", {})
    if status != 200:
        raise Cop0ProbeError(
            f"COP0 BIOS trace start returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    results: dict[str, int] = {}
    for register, expected in EXPECTED_REGISTERS.items():
        try:
            value, _response = call_signed_v0(
                port, deadline, f"GetCop0 register {register}", GET_COP0, register
            )
        except BiosCallError as error:
            raise Cop0ProbeError(str(error)) from error
        if value != expected:
            raise Cop0ProbeError(
                f"GetCop0 register {register} diverged: 0x{value & 0xFFFFFFFFFFFFFFFF:016x}"
            )
        results[str(register)] = value

    status, body = request_bytes(port, "POST", "/bios/trace/capture", {}, timeout=7.0)
    if status != 200:
        raise Cop0ProbeError(
            f"COP0 BIOS trace capture returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    try:
        trace = json.loads(body)
    except json.JSONDecodeError as error:
        raise Cop0ProbeError("COP0 trace returned malformed JSON") from error
    if not isinstance(trace, dict):
        raise Cop0ProbeError("COP0 trace returned a non-object")
    trace["diagnostic_cop0"] = {"function": f"0x{GET_COP0:08x}", "registers": results}
    return trace


def cop0_probe_is_verified(trace: object) -> bool:
    if not isinstance(trace, dict):
        return False
    diagnostic = trace.get("diagnostic_cop0")
    return (
        isinstance(diagnostic, dict)
        and diagnostic.get("function") == f"0x{GET_COP0:08x}"
        and diagnostic.get("registers")
        == {str(register): value for register, value in EXPECTED_REGISTERS.items()}
    )
