"""Guest-owned title-menu lifecycle steps for surfaceless AVP:E probes."""

import time
from collections.abc import Callable

from avpe.input_probe import press_buttons
from avpe.menu_probe import (
    await_menu_transition,
    await_settled_menu_state,
    complete_menu_action,
    menu_state,
    run_ready_menu_action,
)

PAD_START_MASK = 1 << 9


def reach_title_menu(port: int, deadline: float) -> None:
    """Advance from the restored title presentation to a live game menu."""
    press_buttons(port, deadline, PAD_START_MASK)

    last_status = 0
    last_detail = ""
    while time.monotonic() < deadline:
        status, state, detail = menu_state(port)
        if _menu_is_live(status, state):
            return
        if status not in (409, 500):
            raise RuntimeError(
                f"BIOS phase title menu discovery failed: HTTP {status}: {detail}"
            )
        last_status, last_detail = status, detail
        time.sleep(0.05)
    raise RuntimeError(
        "BIOS phase title did not reach a game-owned menu after Start: "
        f"HTTP {last_status}: {last_detail}"
    )


def activate_title_menu(
    port: int, deadline: float, start_trace: Callable[[int], None]
) -> dict[str, object]:
    """Activate the title's current focused item without changing selection."""
    reach_title_menu(port, deadline)
    _, title_menu = await_settled_menu_state(
        port, deadline, "BIOS phase title pre-action menu discovery"
    )
    return _activate_title_selection(
        port, deadline, title_menu, "BIOS phase title physical activation", start_trace
    )


def activate_title_menu_after_down(
    port: int, deadline: float, start_trace: Callable[[int], None]
) -> tuple[dict[str, object], dict[str, object]]:
    """Exercise the separate title directional-action diagnostic before activation."""
    reach_title_menu(port, deadline)
    complete_menu_action(port, deadline, "down", "BIOS phase title profile selection")
    down_status, down_menu = await_settled_menu_state(
        port, deadline, "BIOS phase title post-down menu discovery"
    )
    title_menu = _activate_title_selection(
        port, deadline, down_menu, "BIOS phase title post-down activation", start_trace
    )
    return {"status": down_status, "state": down_menu}, title_menu


def _activate_title_selection(
    port: int,
    deadline: float,
    before: dict[str, object],
    context: str,
    start_trace: Callable[[int], None],
) -> dict[str, object]:
    start_trace(port)
    run_ready_menu_action(
        port,
        deadline,
        "activate",
        before.get("menu_vtable"),
        before.get("focused_item_action"),
    )
    status, title_menu = await_menu_transition(port, deadline, before, context)
    return {"status": status, "state": title_menu}


def _menu_is_live(status: int, state: object) -> bool:
    return bool(
        status == 200
        and isinstance(state, dict)
        and isinstance(state.get("menu"), str)
        and state["menu"] != "0x00000000"
        and isinstance(state.get("callback_count"), int)
        and state["callback_count"] > 0
    )
