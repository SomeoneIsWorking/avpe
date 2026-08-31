"""Grounded physical-pause probe for surfaceless AVP:E control runs."""

import time

from avpe.control_http import request_json
from avpe.menu_probe import menu_state


# PadDualshock2::Inputs::PAD_START. Keep this in the product's input-bit space.
PAD_START_MASK = 1 << 9


def probe_gameplay_pause_menu(port: int, deadline: float) -> dict[str, object]:
    """Press Start from gameplay and require the resulting live game menu."""
    initial_status, initial_menu, initial_detail = menu_state(port)
    if initial_status == 200 and _menu_is_live(initial_menu):
        raise RuntimeError(
            "gameplay pause probe requires no active menu before PAD_START: "
            f"{initial_menu}"
        )
    if initial_status != 409:
        raise RuntimeError(
            "gameplay pause probe could not establish an inactive menu state: "
            f"HTTP {initial_status}: {initial_detail}"
        )

    status, press, detail = request_json(
        port, "POST", "/input/press", {"mask": PAD_START_MASK, "ms": 250}
    )
    if status != 200 or press is None or press.get("pressed") is not True:
        raise RuntimeError(f"PAD_START injection returned HTTP {status}: {detail}")

    last_status = 0
    last_menu: dict[str, object] | None = None
    last_detail = ""
    while time.monotonic() < deadline:
        last_status, candidate, last_detail = menu_state(port)
        if last_status == 200 and _menu_is_live(candidate):
            return {
                "input_route": "physical-pad-start",
                "initial_menu_status": initial_status,
                "press": press,
                "menu": candidate,
            }
        if candidate is not None:
            last_menu = candidate
        if last_status not in (200, 409):
            break
        time.sleep(0.05)
    raise RuntimeError(
        "PAD_START did not open a live game menu: "
        f"last_status={last_status}, last_detail={last_detail}, last_menu={last_menu}"
    )


def _menu_is_live(value: object) -> bool:
    return isinstance(value, dict) and value.get("menu") != "0x00000000" \
        and int(value.get("callback_count", 0)) > 0
