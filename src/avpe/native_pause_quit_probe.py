"""Grounded discovery of the pause-menu Quit confirmation controls."""

import json
import struct

from avpe.control_http import request_bytes
from avpe.native_menu_pointer_dispatch_probe import dispatch_dispatched_menu_pointer_at

LOAD_MENU_ACTION = "0xCA788CFB"
PAUSE_QUIT_TEXT = "Quit"
RENDER_SELECTED_LIST = 0x003B40B0
RENDER_SELECTED_LIST_BYTES = 20_480
RENDER_SELECTED_END = 0x0036706C
RENDER_SELECTION_BYTES = 20
MAX_PAUSE_SELECTION_CANDIDATES = 64
RENDER_SCREEN_WIDTH = 639
RENDER_SCREEN_HEIGHT = 447
MENU_ITEM_ACTION_TARGET_OFFSET = 0x114
MENU_ITEM_TEXT_OFFSET = 0x148
MENU_PARENT_OFFSET = 0x0C
MENU_ITEM_ACTIVATION_VIRTUAL_OFFSET = 0xD8
MAX_MENU_ITEM_TEXT_BYTES = 128


def _read_guest_bytes(port: int, address: int, length: int) -> bytes:
    status, body = request_bytes(port, "GET", f"/mem/read?addr=0x{address:08x}&len={length:x}")
    if status != 200:
        raise RuntimeError(f"guest selection-list read returned HTTP {status} at 0x{address:08x}")
    try:
        response = json.loads(body)
        encoded = response["hex"]
    except (json.JSONDecodeError, KeyError, TypeError):
        raise RuntimeError(f"guest selection-list response is malformed at 0x{address:08x}") from None
    if not isinstance(encoded, str):
        raise TypeError(f"guest selection-list response has non-string bytes at 0x{address:08x}")
    data = bytes.fromhex(encoded)
    if len(data) != length:
        raise RuntimeError(f"guest selection-list read is short at 0x{address:08x}: {len(data)} != {length}")
    return data


def read_guest_word(port: int, address: int) -> int:
    return struct.unpack("<I", _read_guest_bytes(port, address, 4))[0]


def pause_selection_rectangles(port: int) -> list[dict[str, int]]:
    end = read_guest_word(port, RENDER_SELECTED_END)
    limit = RENDER_SELECTED_LIST + RENDER_SELECTED_LIST_BYTES
    if end < RENDER_SELECTED_LIST or end > limit or (end - RENDER_SELECTED_LIST) % RENDER_SELECTION_BYTES:
        raise RuntimeError(f"guest selection-list end is invalid: 0x{end:08x}")
    raw = _read_guest_bytes(port, RENDER_SELECTED_LIST, end - RENDER_SELECTED_LIST)
    return [
        dict(zip(("handle", "xmin", "ymin", "xmax", "ymax"), struct.unpack_from("<IIIII", raw, offset)))
        for offset in range(0, len(raw), RENDER_SELECTION_BYTES)
    ]


def menu_item_action_target(port: int, focus: object) -> int | None:
    if not isinstance(focus, dict):
        return None
    object_text = focus.get("focus_object")
    if not isinstance(object_text, str):
        return None
    try:
        address = int(object_text, 0)
    except ValueError:
        return None
    if address == 0:
        return None
    return read_guest_word(port, address + MENU_ITEM_ACTION_TARGET_OFFSET)


def menu_item_text(port: int, focus: object) -> str | None:
    if not isinstance(focus, dict):
        return None
    object_text = focus.get("focus_object")
    if not isinstance(object_text, str):
        return None
    try:
        address = int(object_text, 0)
    except ValueError:
        return None
    if address == 0:
        return None
    text_address = read_guest_word(port, address + MENU_ITEM_TEXT_OFFSET)
    if text_address == 0:
        return None
    raw = _read_guest_bytes(port, text_address, MAX_MENU_ITEM_TEXT_BYTES)
    terminator = raw.find(b"\0")
    if terminator < 0:
        raise RuntimeError(f"menu item text is not NUL-terminated within {MAX_MENU_ITEM_TEXT_BYTES} bytes")
    try:
        return raw[:terminator].decode("ascii")
    except UnicodeDecodeError:
        raise RuntimeError(f"menu item text is not ASCII at 0x{text_address:08x}") from None


def menu_parent(port: int, menu_state_value: object) -> int | None:
    if not isinstance(menu_state_value, dict):
        return None
    menu_text = menu_state_value.get("menu")
    if not isinstance(menu_text, str):
        return None
    try:
        menu = int(menu_text, 0)
    except ValueError:
        return None
    if menu == 0:
        return None
    return read_guest_word(port, menu + MENU_PARENT_OFFSET)


def menu_parent_action_handler(port: int, parent: int | None) -> dict[str, str] | None:
    if parent is None or parent == 0:
        return None
    vtable = read_guest_word(port, parent)
    if vtable == 0:
        return None
    handler = read_guest_word(port, vtable + MENU_ITEM_ACTIVATION_VIRTUAL_OFFSET)
    return {
        "object": f"0x{parent:08x}",
        "vtable": f"0x{vtable:08x}",
        "item_activated_handler": f"0x{handler:08x}",
    }


def _pause_selection_candidates(selections: list[dict[str, int]]) -> list[dict[str, int]]:
    candidates = [
        selection for selection in selections
        if selection["handle"] != 0
        and selection["xmin"] < selection["xmax"] <= RENDER_SCREEN_WIDTH
        and selection["ymin"] < selection["ymax"] <= RENDER_SCREEN_HEIGHT
    ]
    if not candidates:
        raise RuntimeError(f"pause selection list has no usable native rectangles: {selections}")
    if len(candidates) > MAX_PAUSE_SELECTION_CANDIDATES:
        raise RuntimeError(
            "pause selection list exceeds the bounded Quit confirmation probe corpus: "
            f"{len(candidates)} > {MAX_PAUSE_SELECTION_CANDIDATES}; selections={selections}")
    return candidates


def focus_pause_selection(
    port: int,
    deadline: float,
    selections: list[dict[str, int]],
    action: str | None,
    text: str | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Focus one item identified by its live text and action, never by screen coordinates."""
    observed: list[dict[str, object]] = []
    for selection in _pause_selection_candidates(selections):
        screen_x = (selection["xmin"] + selection["xmax"]) / 2.0
        screen_y = (selection["ymin"] + selection["ymax"]) / 2.0
        pointer = dispatch_dispatched_menu_pointer_at(port, deadline, screen_x, screen_y)
        state = pointer["state"]
        assert isinstance(state, dict)
        observation = {
            "selection": selection,
            "screen_x": screen_x,
            "screen_y": screen_y,
            "focus": state.get("before"),
            "focused_item_action": state.get("focused_item_action"),
            "focused_item_action_target": menu_item_action_target(port, state.get("before")),
            "focused_item_text": menu_item_text(port, state.get("before")),
        }
        observed.append(observation)
        if (action is None or state.get("focused_item_action") == action) \
                and (text is None or observation["focused_item_text"] == text):
            return {"pointer": pointer, **observation}, observed
    raise RuntimeError(
        "BIOS phase shutdown pointer scan found no grounded selection: "
        f"action={action}, text={text!r}, observed={observed}")
