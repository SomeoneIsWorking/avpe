"""Bounded invalid-token diagnostics for the EE sceSifDmaStat wrapper."""

from __future__ import annotations

import json

from avpe.control_http import request_bytes
from avpe.native_bios_call import BiosCallError, call_signed_v0


SIF_DMA_STAT = 0x002B41C0
INVALID_DMA_TOKEN = 0xFFFFFFFF
EXPECTED_RESULT = -1


class SifDmaProbeError(RuntimeError):
    """The bounded invalid-DMA-status phase did not establish its contract."""


def probe_invalid_sif_dma(port: int, deadline: float) -> dict[str, object]:
    """Capture the grounded invalid-token status without creating DMA state."""
    status, body = request_bytes(port, "POST", "/bios/trace/start", {})
    if status != 200:
        raise SifDmaProbeError(
            f"SIF-DMA BIOS trace start returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    try:
        result, _response = call_signed_v0(
            port, deadline, "invalid_sif_dma_token", SIF_DMA_STAT, INVALID_DMA_TOKEN
        )
    except BiosCallError as error:
        raise SifDmaProbeError(str(error)) from error
    if result != EXPECTED_RESULT:
        raise SifDmaProbeError(f"invalid SIF-DMA result diverged: {result}")

    status, body = request_bytes(port, "POST", "/bios/trace/capture", {}, timeout=7.0)
    if status != 200:
        raise SifDmaProbeError(
            f"SIF-DMA BIOS trace capture returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )
    try:
        trace = json.loads(body)
    except json.JSONDecodeError as error:
        raise SifDmaProbeError("SIF-DMA trace returned malformed JSON") from error
    if not isinstance(trace, dict):
        raise SifDmaProbeError("SIF-DMA trace returned a non-object")
    trace["diagnostic_sif_dma"] = {
        "token": f"0x{INVALID_DMA_TOKEN:08x}",
        "result": result,
    }
    return trace


def sif_dma_probe_is_verified(trace: object) -> bool:
    if not isinstance(trace, dict):
        return False
    diagnostic = trace.get("diagnostic_sif_dma")
    return isinstance(diagnostic, dict) \
        and diagnostic.get("token") == "0xffffffff" \
        and diagnostic.get("result") == EXPECTED_RESULT
