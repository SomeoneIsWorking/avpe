"""Bounded guest-memory buffer transport for native BIOS probes."""

from __future__ import annotations

import json

from avpe.control_http import request_bytes, request_json


class GuestBufferError(RuntimeError):
    """A diagnostic guest-memory buffer operation failed or returned bad data."""


def write_guest_buffer(port: int, address: int, data_hex: str) -> None:
    if address < 0 or address > 0xFFFFFFFF or not data_hex \
            or len(data_hex) % 2 != 0 or len(data_hex) > 8192:
        raise GuestBufferError("invalid guest buffer seed")
    try:
        bytes.fromhex(data_hex)
    except ValueError as error:
        raise GuestBufferError("guest buffer seed is not hexadecimal") from error
    status, response, detail = request_json(
        port,
        "POST",
        "/mem/write",
        {"addr": f"0x{address:08x}", "hex": data_hex},
    )
    if status != 200:
        raise GuestBufferError(f"guest buffer write returned HTTP {status}: {detail}")
    if response is None or response.get("written") != len(data_hex) // 2:
        raise GuestBufferError("guest buffer write returned an incomplete byte count")


def read_guest_buffer(port: int, address: int, size: int) -> str:
    if address < 0 or address > 0xFFFFFFFF or size <= 0 or size > 4096:
        raise GuestBufferError("invalid guest buffer read")
    status, body = request_bytes(
        port,
        "GET",
        f"/mem/read?addr=0x{address:08x}&len=0x{size:x}",
        timeout=3.0,
    )
    if status != 200:
        raise GuestBufferError(
            f"guest buffer read returned HTTP {status}: {body.decode(errors='replace').strip()}"
        )
    try:
        response = json.loads(body)
    except json.JSONDecodeError as error:
        raise GuestBufferError("guest buffer read returned malformed JSON") from error
    if not isinstance(response, dict) or not isinstance(response.get("hex"), str):
        raise GuestBufferError("guest buffer read omitted its hex buffer")
    output_hex = response["hex"]
    if len(output_hex) != size * 2:
        raise GuestBufferError(f"guest buffer read returned {len(output_hex) // 2} bytes")
    return output_hex
