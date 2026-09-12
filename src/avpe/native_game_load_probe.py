"""Grounded normal game-load BIOS/IOP capture policy."""

import json
import time
from collections.abc import Callable

from avpe.control_http import request_bytes
from avpe.menu_probe import (
    await_menu_transition,
    await_settled_menu_state,
    complete_menu_action,
    menu_state,
)
from avpe.native_menu_pointer_dispatch_probe import (
    activate_focused_dispatched_menu_pointer,
)
from avpe.native_pause_probe import probe_gameplay_pause_menu
from avpe.native_pause_quit_probe import (
    LOAD_MENU_ACTION,
    focus_pause_selection,
    menu_item_text,
    pause_selection_rectangles,
)

GAME_LOAD_TRACE_ENTRY_PC = 0x00130000
GAME_LOAD_TRACE_RETURN_PC = 0x00130168
GAME_LOAD_PACIFY_PROCESS_PC = 0x00202C20
GAME_LOAD_MENU_VTABLE = "0x00341620"
LOAD_CONFIRMATION_MENU_VTABLE = "0x00340930"
MISSION_GOALS_MENU_VTABLE = "0x00342570"
SLOT_ENUMERATION_OWNER_PC = 0x00130800


class BiosGameLoadCaptureError(RuntimeError):
    def __init__(self, message: str, trace: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.trace = trace


def game_load_boundary_is_verified(trace: object) -> bool:
    from avpe.native_bios_probe import bios_trace_is_verified

    if not bios_trace_is_verified(trace) or not isinstance(trace, dict):
        return False
    boundary = trace.get("game_load_boundary")
    if not isinstance(boundary, dict) or any((
        boundary.get("entry_pc") != GAME_LOAD_TRACE_ENTRY_PC,
        boundary.get("return_pc") != GAME_LOAD_TRACE_RETURN_PC,
        boundary.get("pacify_process_pc") != GAME_LOAD_PACIFY_PROCESS_PC,
        isinstance(boundary.get("pacify_process_calls"), bool),
        not isinstance(boundary.get("pacify_process_calls"), int),
        boundary.get("pacify_process_calls", 0) <= 0,
        boundary.get("complete") is not True,
        boundary.get("succeeded") is not True,
        boundary.get("result") != 0,
        boundary.get("sequence_errors") != 0,
    )):
        return False
    return _ordered_boundary_points_are_verified(boundary)


def start_bios_game_load_phase(port: int) -> None:
    status, body = request_bytes(port, "POST", "/bios/trace/start-game-load", {})
    if status != 200:
        raise RuntimeError(
            "BIOS game-load trace start returned HTTP "
            f"{status}: {body.decode(errors='replace').strip()}"
        )


def capture_bios_game_load_boundary(port: int) -> dict[str, object]:
    from avpe.native_bios_probe import bios_trace_failure_detail

    status, body = request_bytes(
        port, "POST", "/bios/trace/capture-game-load", {}, timeout=22.0
    )
    try:
        trace = json.loads(body)
    except json.JSONDecodeError:
        trace = None
    if status != 200:
        raise BiosGameLoadCaptureError(
            f"BIOS game-load trace capture returned HTTP {status}: "
            f"{bios_trace_failure_detail(trace)}",
            trace if isinstance(trace, dict) else None,
        )
    if not game_load_boundary_is_verified(trace):
        raise BiosGameLoadCaptureError(
            "complete grounded game-load boundary was not observed: "
            f"{bios_trace_failure_detail(trace)}",
            trace if isinstance(trace, dict) else None,
        )
    assert isinstance(trace, dict)
    return trace


def run_game_load_phase(
    port: int,
    deadline: float,
) -> tuple[dict[str, object], str, str]:
    preparation = _prepare_game_load_confirmation(port, deadline)
    start_bios_game_load_phase(port)
    confirmation_activation = complete_menu_action(
        port, deadline, "activate", "BIOS phase game-load confirmation activation"
    )
    mission_modal = _await_mission_goals_modal(port, deadline)
    mission_modal_activation = complete_menu_action(
        port, deadline, "activate", "BIOS phase game-load mission-goals exit"
    )
    fields = {
        "game_load_preparation": preparation,
        "game_load_confirmation_activation": confirmation_activation,
        "game_load_mission_modal": mission_modal,
        "game_load_mission_modal_activation": mission_modal_activation,
    }
    try:
        trace = capture_bios_game_load_boundary(port)
    except BiosGameLoadCaptureError as error:
        if error.trace is not None:
            error.trace.update(fields)
        raise
    trace.update(fields)
    return (
        trace,
        "gameplay_to_game_load",
        "pause_load_slot_confirm_to_cprofile_load_game",
    )


def run_slot_enumeration_phase(
    port: int,
    deadline: float,
) -> tuple[dict[str, object], str, str]:
    """Capture the card reads performed while constructing GLoadGameMenu."""
    from avpe.native_bios_probe import capture_bios_trace, start_bios_trace

    preparation = _prepare_game_load_menu(port, deadline, start_bios_trace)
    trace = capture_bios_trace(port, at_guest_boundary=False)
    counts = _import_counts(trace)
    if counts.get("mcman.McRead", 0) <= 0:
        raise RuntimeError(
            "slot enumeration did not observe mcman.McRead: "
            f"counts={counts}"
        )
    if counts.get("mcman.McGetDir", 0) <= 0:
        raise RuntimeError(
            "slot enumeration did not observe the grounded mcman directory read: "
            f"counts={counts}"
        )
    trace["slot_enumeration"] = {
        "owner_pc": SLOT_ENUMERATION_OWNER_PC,
        "menu_vtable": GAME_LOAD_MENU_VTABLE,
        "import_counts": counts,
        "sync_wrapper_pc": 0x002C0580,
        "complete": True,
    }
    trace["game_load_preparation"] = preparation
    return trace, "gameplay_to_slot_enumeration", "build_game_list_card_scan"


def _prepare_game_load_confirmation(port: int, deadline: float) -> dict[str, object]:
    preparation = _prepare_game_load_menu(port, deadline)
    load_menu = preparation["load_menu"]
    slot_text = menu_item_text(port, load_menu)
    slot_activation = complete_menu_action(
        port, deadline, "activate", "BIOS phase game-load slot activation"
    )
    confirmation_status, confirmation_menu = await_menu_transition(
        port,
        deadline,
        load_menu,
        "BIOS phase game-load confirmation transition",
    )
    _require_menu(
        confirmation_status,
        confirmation_menu,
        LOAD_CONFIRMATION_MENU_VTABLE,
        "load confirmation menu",
    )
    confirmation_focus = _focus_confirmation_yes(port, deadline, confirmation_menu)
    preparation.update({
        "slot_text": slot_text,
        "slot_activation": slot_activation,
        "confirmation_menu": confirmation_menu,
        "confirmation_focus": confirmation_focus,
    })
    return preparation


def _prepare_game_load_menu(
    port: int,
    deadline: float,
    before_load_activation: Callable[[int], None] | None = None,
) -> dict[str, object]:
    pause = probe_gameplay_pause_menu(port, deadline)
    pause_selections = pause_selection_rectangles(port)
    load_item, load_observations = focus_pause_selection(
        port, deadline, pause_selections, LOAD_MENU_ACTION, "Load"
    )
    if before_load_activation is not None:
        before_load_activation(port)
    load_activation = activate_focused_dispatched_menu_pointer(port, deadline)
    load_status, load_menu = await_settled_menu_state(
        port, deadline, "BIOS phase game-load slot menu readiness"
    )
    _require_menu(load_status, load_menu, GAME_LOAD_MENU_VTABLE, "GLoadGameMenu")
    return {
        "pause": pause,
        "pause_selections": pause_selections,
        "load_item": load_item,
        "load_observations": load_observations,
        "load_activation": load_activation,
        "load_menu": load_menu,
    }


def _import_counts(trace: dict[str, object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in trace.get("events", []):
        if not isinstance(event, dict) or event.get("kind") != "import":
            continue
        library, function = event.get("library"), event.get("function")
        calls = event.get("calls", 0)
        if not isinstance(library, str) or not isinstance(function, str) \
                or not isinstance(calls, int) or isinstance(calls, bool):
            continue
        if function == "unknown" and isinstance(event.get("ordinal"), int):
            function = f"unknown[{event['ordinal']}]"
        key = f"{library}.{function}"
        counts[key] = counts.get(key, 0) + calls
    return counts


def _focus_confirmation_yes(
    port: int,
    deadline: float,
    confirmation_menu: dict[str, object],
) -> dict[str, object]:
    before_text = menu_item_text(port, confirmation_menu)
    if before_text == "Yes":
        return {"before_text": before_text, "action": None, "after": confirmation_menu}
    if before_text != "No":
        raise RuntimeError(
            "BIOS phase game-load confirmation has no grounded Yes/No focus: "
            f"text={before_text!r}, state={confirmation_menu}"
        )
    completion = complete_menu_action(
        port, deadline, "left", "BIOS phase game-load confirmation Yes focus"
    )
    status, after = await_settled_menu_state(
        port, deadline, "BIOS phase game-load confirmation focus readiness"
    )
    _require_menu(
        status, after, LOAD_CONFIRMATION_MENU_VTABLE, "load confirmation menu"
    )
    after_text = menu_item_text(port, after)
    if after_text != "Yes":
        raise RuntimeError(
            "BIOS phase game-load confirmation did not focus Yes: "
            f"text={after_text!r}, state={after}"
        )
    return {
        "before_text": before_text,
        "action": "left",
        "completion": completion,
        "after_text": after_text,
        "after": after,
    }


def _await_mission_goals_modal(port: int, deadline: float) -> dict[str, object]:
    last_status = 0
    last_detail = ""
    last_state: dict[str, object] | None = None
    while time.monotonic() < deadline:
        status, state, detail = menu_state(port)
        last_status, last_detail, last_state = status, detail, state
        if (
            status == 200
            and state is not None
            and state.get("source") == "mission-goals-load"
            and state.get("menu_vtable") == MISSION_GOALS_MENU_VTABLE
        ):
            return state
        if status not in (200, 409, 500):
            break
        time.sleep(0.05)
    raise RuntimeError(
        "BIOS phase game-load did not reach the grounded mission-goals modal: "
        f"HTTP {last_status}: {last_detail}; last_state={last_state}"
    )


def _require_menu(
    status: int,
    state: dict[str, object],
    expected_vtable: str,
    description: str,
) -> None:
    if (
        status != 200
        or state.get("menu_vtable") != expected_vtable
        or state.get("focus_object") == "0x00000000"
        or state.get("focused_item_action_valid") is not True
    ):
        raise RuntimeError(
            f"BIOS phase game-load did not reach the grounded {description}: "
            f"status={status}, state={state}"
        )


def _ordered_boundary_points_are_verified(boundary: dict[str, object]) -> bool:
    entry = boundary.get("entry")
    returned = boundary.get("return")
    if not isinstance(entry, dict) or not isinstance(returned, dict) or any((
        entry.get("pc") != GAME_LOAD_TRACE_ENTRY_PC,
        returned.get("pc") != GAME_LOAD_TRACE_RETURN_PC,
    )):
        return False
    for field in ("ee_cycle", "iop_cycle", "frame", "host_time_ns"):
        if (
            isinstance(entry.get(field), bool)
            or not isinstance(entry.get(field), int)
            or isinstance(returned.get(field), bool)
            or not isinstance(returned.get(field), int)
        ):
            return False
    return bool(
        returned["ee_cycle"] > entry["ee_cycle"]
        and returned["iop_cycle"] >= entry["iop_cycle"]
        and returned["frame"] >= entry["frame"]
        and returned["host_time_ns"] > entry["host_time_ns"]
    )
