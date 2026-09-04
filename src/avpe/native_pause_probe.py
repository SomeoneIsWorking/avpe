"""Grounded physical-pause probe for surfaceless AVP:E control runs."""

import time

from avpe.input_probe import press_buttons
from avpe.menu_probe import input_dispatch_state, menu_input_dispatch_count, menu_state


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
    dispatch_status, initial_dispatch, dispatch_detail = input_dispatch_state(port)
    if dispatch_status != 200 or initial_dispatch is None:
        raise RuntimeError(
            "gameplay pause probe could not inspect the normal input dispatch: "
            f"HTTP {dispatch_status}: {dispatch_detail}"
        )

    press = press_buttons(port, deadline, PAD_START_MASK)

    last_status = 0
    last_menu: dict[str, object] | None = None
    last_detail = ""
    while time.monotonic() < deadline:
        last_status, candidate, last_detail = menu_state(port)
        if last_status == 200 and _menu_is_live(candidate):
            dispatch_status, dispatch, dispatch_detail = input_dispatch_state(port)
            if dispatch_status != 200 or dispatch is None:
                raise RuntimeError(
                    "gameplay pause probe could not inspect the post-pause input dispatch: "
                    f"HTTP {dispatch_status}: {dispatch_detail}"
                )
            callback = _post_pause_menu_dispatch(initial_dispatch, dispatch, candidate)
            if callback is not None:
                return {
                    "input_route": "physical-pad-start",
                    "initial_menu_status": initial_status,
                    "press": press,
                    "menu": candidate,
                    "post_pause_menu_dispatch": callback,
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


def _post_pause_menu_dispatch(
    before: dict[str, object],
    after: dict[str, object],
    menu: dict[str, object],
) -> dict[str, object] | None:
    """Return the first post-pause game-owned menu-input callback."""
    menu_address = menu.get("menu")
    baseline = menu_input_dispatch_count(before, menu_address)
    for callback in after.get("callbacks", []):
        if not isinstance(callback, dict):
            continue
        dispatches = callback.get("dispatches")
        if menu_input_dispatch_count({"callbacks": [callback]}, menu_address) > baseline \
                and isinstance(dispatches, int) and not isinstance(dispatches, bool):
            return callback
    return None
