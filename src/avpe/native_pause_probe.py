"""Grounded physical-pause probe for surfaceless AVP:E control runs."""

import math
import struct
import time
from typing import TypedDict

from avpe.input_probe import press_buttons
from avpe.menu_probe import input_dispatch_state, menu_input_dispatch_count, menu_state
from avpe.native_guest_buffer import read_guest_buffer


# PadDualshock2::Inputs::PAD_START. Keep this in the product's input-bit space.
PAD_START_MASK = 1 << 9
# SLUS-20147 symbols and GPauseHandler::Input_Pause's first admission guard.
PAUSE_HANDLER_SINGLETON = 0x00367AD4
PAUSE_HANDLER_VTABLE = 0x00342220
GAME_TIME = 0x003673A4
PAUSE_ENABLED_AT_OFFSET = 0x3C


class PauseReadiness(TypedDict):
    game_time: float
    enabled_at: float
    ready: bool


def _guest_word(port: int, address: int) -> int:
    return struct.unpack("<I", bytes.fromhex(read_guest_buffer(port, address, 4)))[0]


def _guest_float(port: int, address: int) -> float:
    return struct.unpack("<f", struct.pack("<I", _guest_word(port, address)))[0]


def _pause_readiness(port: int) -> PauseReadiness:
    handler = _guest_word(port, PAUSE_HANDLER_SINGLETON)
    if handler == 0 or _guest_word(port, handler) != PAUSE_HANDLER_VTABLE:
        raise RuntimeError(f"live GPauseHandler is unavailable: 0x{handler:08x}")
    game_time = _guest_float(port, GAME_TIME)
    enabled_at = _guest_float(port, handler + PAUSE_ENABLED_AT_OFFSET)
    if not math.isfinite(game_time) or not math.isfinite(enabled_at):
        raise RuntimeError(
            f"invalid GPauseHandler timer: game_time={game_time}, enabled_at={enabled_at}"
        )
    return {
        "game_time": game_time,
        "enabled_at": enabled_at,
        "ready": game_time >= enabled_at,
    }


def _await_pause_readiness(
    port: int, deadline: float
) -> tuple[PauseReadiness, PauseReadiness]:
    """Poll the live guest guard before issuing the one physical Start edge."""
    initial = _pause_readiness(port)
    current = initial
    while not current["ready"] and time.monotonic() < deadline:
        time.sleep(0.05)
        current = _pause_readiness(port)
    if not current["ready"]:
        raise RuntimeError(
            "GPauseHandler did not admit Pause before the probe deadline: "
            f"initial={initial}, last={current}"
        )
    return initial, current


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

    initial_readiness, admitted_readiness = _await_pause_readiness(port, deadline)
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
                    "pause_readiness": {
                        "initial": initial_readiness,
                        "admitted": admitted_readiness,
                    },
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
