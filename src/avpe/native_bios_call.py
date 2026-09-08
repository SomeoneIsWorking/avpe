"""Shared bounded EE-call transport for BIOS diagnostic phases."""

from __future__ import annotations

import time
from typing import Any

from avpe.control_http import request_json


class BiosCallError(RuntimeError):
    """A diagnostic EE call could not produce a restored, typed result."""


def call_signed_v0(
    port: int,
    deadline: float,
    label: str,
    function: int,
    argument: int = 0,
    stack_hex: str | None = None,
) -> tuple[int, dict[str, Any]]:
    if time.monotonic() >= deadline:
        raise BiosCallError(f"diagnostic EE-call deadline expired before {label}")
    payload: dict[str, object] = {"function": f"0x{function:08x}", "a0": argument}
    if stack_hex is not None:
        payload.update(stack_argument=0, stack_hex=stack_hex)
    status, response, detail = request_json(port, "POST", "/ee/call", payload)
    if status != 200 or response is None:
        raise BiosCallError(f"{label} returned HTTP {status}: {detail}")
    if response.get("stack_restored") is not True:
        raise BiosCallError(f"{label} did not restore the guest stack")
    value = response.get("v0")
    if not isinstance(value, str):
        raise BiosCallError(f"{label} returned a non-hex v0")
    try:
        raw = int(value, 16)
    except ValueError as error:
        raise BiosCallError(f"{label} returned malformed v0") from error
    if not 0 <= raw <= 0xFFFFFFFFFFFFFFFF:
        raise BiosCallError(f"{label} returned an out-of-range v0")
    signed = raw - (1 << 64) if raw & (1 << 63) else raw
    return signed, response
