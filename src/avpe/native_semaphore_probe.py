"""Bounded BIOS semaphore diagnostics for the AVP:E control channel."""

from __future__ import annotations

import json
import struct
import time
from typing import Any

from avpe.control_http import request_bytes, request_json


CREATE_SEMA = 0x002B3E20
DELETE_SEMA = 0x002B3E30
SIGNAL_SEMA = 0x002B3E40
POLL_SEMA = 0x002B3E70
INVALID_ID = 0xFFFFFFFF
DESCRIPTOR = struct.pack("<6I", 0, 1, 0, 0, 0, 0)


class SemaphoreProbeError(RuntimeError):
    """The bounded diagnostic sequence did not establish its contract."""


def _signed_v0(response: dict[str, Any], label: str) -> int:
    if response.get("stack_restored") is not True:
        raise SemaphoreProbeError(f"{label} did not restore the guest stack")
    value = response.get("v0")
    if not isinstance(value, str):
        raise SemaphoreProbeError(f"{label} returned a non-hex v0")
    try:
        raw = int(value, 16)
    except ValueError as error:
        raise SemaphoreProbeError(f"{label} returned malformed v0") from error
    if not 0 <= raw <= 0xFFFFFFFFFFFFFFFF:
        raise SemaphoreProbeError(f"{label} returned an out-of-range v0")
    return raw - (1 << 64) if raw & (1 << 63) else raw


def _call(port: int, deadline: float, label: str, function: int, argument: int = 0,
          stack_hex: str | None = None) -> tuple[int, dict[str, Any]]:
    if time.monotonic() >= deadline:
        raise SemaphoreProbeError(f"semaphore probe deadline expired before {label}")
    payload: dict[str, object] = {"function": f"0x{function:08x}", "a0": argument}
    if stack_hex is not None:
        payload.update(stack_argument=0, stack_hex=stack_hex)
    status, response, detail = request_json(port, "POST", "/ee/call", payload)
    if status != 200 or response is None:
        raise SemaphoreProbeError(f"{label} returned HTTP {status}: {detail}")
    return _signed_v0(response, label), response


def probe_semaphore_lifecycle(port: int, deadline: float) -> dict[str, object]:
    """Run private, nonblocking semaphore operations and capture the census."""
    status, body = request_bytes(port, "POST", "/bios/trace/start", {})
    if status != 200:
        raise SemaphoreProbeError(
            f"semaphore BIOS trace start returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )

    invalid: dict[str, int] = {}
    for label, function in (
        ("poll_invalid", POLL_SEMA),
        ("signal_invalid", SIGNAL_SEMA),
        ("delete_invalid", DELETE_SEMA),
    ):
        invalid[label], _ = _call(port, deadline, label, function, INVALID_ID)
    if any(value != -1 for value in invalid.values()):
        raise SemaphoreProbeError(f"invalid semaphore ID results were not -1: {invalid}")

    semaphore_id, _ = _call(
        port, deadline, "create", CREATE_SEMA, stack_hex=DESCRIPTOR.hex()
    )
    if semaphore_id <= 0 or semaphore_id > 0x7FFFFFFF:
        raise SemaphoreProbeError(f"CreateSema returned invalid private ID {semaphore_id}")

    operations: dict[str, int] = {"create": semaphore_id}
    for label, function in (
        ("poll_empty", POLL_SEMA),
        ("signal", SIGNAL_SEMA),
        ("signal_full", SIGNAL_SEMA),
        ("poll_available", POLL_SEMA),
        ("poll_after_one", POLL_SEMA),
        ("delete", DELETE_SEMA),
    ):
        operations[label], _ = _call(port, deadline, label, function, semaphore_id)
    if operations["poll_empty"] != -1:
        raise SemaphoreProbeError(f"empty semaphore poll did not return -1: {operations}")
    if any(operations[label] != semaphore_id for label in (
        "signal", "signal_full", "poll_available", "poll_after_one", "delete"
    )):
        raise SemaphoreProbeError(f"semaphore lifecycle results diverged: {operations}")

    status, body = request_bytes(port, "POST", "/bios/trace/capture", {}, timeout=7.0)
    if status != 200:
        raise SemaphoreProbeError(
            f"semaphore BIOS trace capture returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    try:
        trace = json.loads(body)
    except json.JSONDecodeError as error:
        raise SemaphoreProbeError("semaphore BIOS trace capture returned malformed JSON") from error
    if not isinstance(trace, dict):
        raise SemaphoreProbeError("semaphore BIOS trace capture returned a non-object")
    trace["diagnostic_semaphore"] = {
        "descriptor_hex": DESCRIPTOR.hex(),
        "invalid_id": invalid,
        "operations": operations,
    }
    return trace


def semaphore_probe_is_verified(trace: object) -> bool:
    """Validate probe-specific evidence without reimplementing trace validation."""
    if not isinstance(trace, dict):
        return False
    diagnostic = trace.get("diagnostic_semaphore")
    if not isinstance(diagnostic, dict) \
            or diagnostic.get("descriptor_hex") != DESCRIPTOR.hex():
        return False
    invalid = diagnostic.get("invalid_id")
    operations = diagnostic.get("operations")
    if not isinstance(invalid, dict) or not isinstance(operations, dict):
        return False
    if any(invalid.get(label) != -1 for label in ("poll_invalid", "signal_invalid", "delete_invalid")):
        return False
    semaphore_id = operations.get("create")
    if not isinstance(semaphore_id, int) or isinstance(semaphore_id, bool) \
            or not 0 < semaphore_id <= 0x7FFFFFFF:
        return False
    if operations.get("poll_empty") != -1:
        return False
    return all(operations.get(label) == semaphore_id for label in (
        "signal", "signal_full", "poll_available", "poll_after_one", "delete"
    ))
