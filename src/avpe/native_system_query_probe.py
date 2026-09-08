"""Bounded EE system-query diagnostics for the AVP:E BIOS inventory."""

from __future__ import annotations

import json

from avpe.control_http import request_bytes
from avpe.native_bios_call import BiosCallError, call_signed_v0


GET_THREAD_ID = 0x002B3D10
END_OF_HEAP = 0x002B3E00
GET_GS_H_PARAM = 0x002B3EE0
GET_GS_V_PARAM = 0x002B3EF0
GS_GET_IMR = 0x002B4140
PS_MODE = 0x002B4260
MACHINE_TYPE = 0x002B4270
GET_MEMORY_SIZE = 0x002B4280
EXPECTED_RESULTS = {
    "get_thread_id": 0x0000000000000001,
    "end_of_heap": 0x0000000001FF5000,
    "get_gs_h_param": 0x0000000000000000,
    "get_gs_v_param": 0x0000000000000080,
    "gs_get_imr": 0x000000000000FF00,
    "machine_type": 0x0000000000008000,
    "get_memory_size": 0x0000000002000000,
}
VOID_QUERIES = ("ps_mode",)


class SystemQueryProbeError(RuntimeError):
    """The bounded EE system-query phase did not establish its contract."""


def probe_system_queries(port: int, deadline: float) -> dict[str, object]:
    """Capture grounded no-argument query results without changing guest state."""
    status, body = request_bytes(port, "POST", "/bios/trace/start", {})
    if status != 200:
        raise SystemQueryProbeError(
            f"system-query BIOS trace start returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    results: dict[str, int] = {}
    void_queries: list[str] = []
    for label, function in (
        ("get_thread_id", GET_THREAD_ID),
        ("end_of_heap", END_OF_HEAP),
        ("get_gs_h_param", GET_GS_H_PARAM),
        ("get_gs_v_param", GET_GS_V_PARAM),
        ("gs_get_imr", GS_GET_IMR),
        ("ps_mode", PS_MODE),
        ("machine_type", MACHINE_TYPE),
        ("get_memory_size", GET_MEMORY_SIZE),
    ):
        try:
            value, _response = call_signed_v0(port, deadline, label, function)
        except BiosCallError as error:
            raise SystemQueryProbeError(str(error)) from error
        if label in VOID_QUERIES:
            void_queries.append(label)
        else:
            results[label] = value
    if results != EXPECTED_RESULTS:
        raise SystemQueryProbeError(f"system-query results diverged: {results}")

    status, body = request_bytes(port, "POST", "/bios/trace/capture", {}, timeout=7.0)
    if status != 200:
        raise SystemQueryProbeError(
            f"system-query BIOS trace capture returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    try:
        trace = json.loads(body)
    except json.JSONDecodeError as error:
        raise SystemQueryProbeError("system-query trace returned malformed JSON") from error
    if not isinstance(trace, dict):
        raise SystemQueryProbeError("system-query trace returned a non-object")
    trace["diagnostic_system_query"] = {
        "results": results,
        "void_queries": void_queries,
    }
    return trace


def system_query_probe_is_verified(trace: object) -> bool:
    if not isinstance(trace, dict):
        return False
    diagnostic = trace.get("diagnostic_system_query")
    return isinstance(diagnostic, dict) \
        and diagnostic.get("results") == EXPECTED_RESULTS \
        and diagnostic.get("void_queries") == list(VOID_QUERIES)
