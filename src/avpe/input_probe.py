"""Physical controller injection helpers for surfaceless AVP:E probes."""

import json
import time

from avpe.control_http import request_bytes, request_json


def button_injection_state(port: int) -> tuple[int, dict[str, object] | None, str]:
    """Read the shipping control channel's active synthetic button mask."""
    status, body = request_bytes(port, "GET", "/debug")
    detail = body.decode(errors="replace").strip()
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return status, None, detail
    if not isinstance(parsed, dict) or _hex_u32(parsed.get("inject")) is None:
        return status, None, detail
    return status, parsed, detail


def press_buttons(
    port: int,
    deadline: float,
    mask: int,
    duration_ms: int = 250,
) -> dict[str, object]:
    """Inject a physical-pad hold and return only after its observed release."""
    if isinstance(mask, bool) or not isinstance(mask, int) or not 0 < mask <= 0xFFFF:
        raise ValueError(f"button injection mask is outside the u16 range: {mask!r}")
    initial = _require_injection_state(port, "before button injection")
    if _hex_u32(initial["inject"]) != 0:
        raise RuntimeError(f"button injection was already active: {initial}")

    status, response, detail = request_json(
        port, "POST", "/input/press", {"mask": mask, "ms": duration_ms}
    )
    if status != 200 or response is None or response.get("pressed") is not True:
        raise RuntimeError(f"button injection returned HTTP {status}: {detail}")

    active: dict[str, object] | None = None
    last_state: dict[str, object] | None = None
    while time.monotonic() < deadline:
        state = _require_injection_state(port, "during button injection")
        last_state = state
        observed_mask = _hex_u32(state["inject"])
        if observed_mask not in (0, mask):
            raise RuntimeError(
                "button injection exposed a different active mask: "
                f"expected=0x{mask:04x}, state={state}"
            )
        if observed_mask == mask:
            active = state
        elif active is not None:
            return {
                "request": response,
                "active": active,
                "released": state,
            }
        time.sleep(0.01)
    raise RuntimeError(
        "button injection did not expose both active and released states: "
        f"active={active}, last_state={last_state}"
    )


def _require_injection_state(port: int, description: str) -> dict[str, object]:
    status, state, detail = button_injection_state(port)
    if status != 200 or state is None:
        raise RuntimeError(
            f"{description} returned invalid button state: HTTP {status}: {detail}"
        )
    return state


def _hex_u32(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = int(value, 16)
    except ValueError:
        return None
    return parsed if 0 <= parsed <= 0xFFFFFFFF else None
