"""Surfaceless BIOS/IOP census polling and proof policy."""

import argparse
import json
import sys
import time
from pathlib import Path

from avpe.bios_result import event_result_is_verified
from avpe.control_http import request_bytes, request_json
from avpe.menu_probe import (
    await_menu_transition as _await_menu_transition,
    await_settled_menu_state as _await_settled_menu_state,
    await_deferred_call,
    await_different_menu_input_dispatch,
    await_dispatched_menu_action,
    await_following_menu_input_dispatch,
    complete_menu_action as _complete_menu_action,
    menu_action,
    menu_state,
)
from avpe.native_asset_probe import await_native_stream_reads
from avpe.native_game_load_probe import (
    BiosGameLoadCaptureError,
    run_game_load_phase,
)
from avpe.native_mission_probe import probe_marine_m1_transition
from avpe.native_menu_pointer_dispatch_probe import (
    activate_focused_dispatched_menu_pointer,
    focus_dispatched_menu_pointer,
)
from avpe.native_pause_probe import probe_gameplay_pause_menu
from avpe.native_pause_quit_probe import (
    LOAD_MENU_ACTION,
    PAUSE_QUIT_TEXT,
    focus_pause_selection as _focus_pause_selection,
    menu_parent as _menu_parent,
    menu_parent_action_handler as _menu_parent_action_handler,
    pause_selection_rectangles as _pause_selection_rectangles,
    read_guest_word,
)
from avpe.native_title_probe import (
    activate_title_menu as _activate_title_menu,
    activate_title_menu_after_down as _activate_title_menu_after_down,
    reach_title_menu as _reach_title_menu,
)

BIOS_TRACE_SCHEMA = "avpe-bios-trace-v6"
TITLE_MENU_ACTIONS = frozenset(("up", "down", "left", "right", "activate", "cancel"))
STATEFILE_BIOS_PHASES = (
    "title",
    "title-down",
    "title-down-activate",
    "title-profile",
    "menu",
    "save-load",
    "game-save",
    "game-load",
    "shutdown",
    "shutdown-pointer",
)
BIOS_EVENT_KINDS = frozenset(
    {
        "ee_syscall",
        "ee_syscall_return",
        "exception",
        "import",
        "iop_import_return",
        "interrupt",
        "module",
        "rpc",
        "timer",
    }
)
MISSION_TRACE_ENTRY_PC = 0x0016F910
MISSION_TRACE_RETURN_PC = 0x0016FA4C
GAME_SAVE_TRACE_ENTRY_PC = 0x00130170
GAME_SAVE_TRACE_RETURN_PC = 0x00130374
GAME_SAVE_PACIFY_PROCESS_PC = 0x00202F40
GAME_SAVE_MENU_VTABLE = "0x00341520"
EMPTY_GAME_SAVE_SLOT_ACTION = "0x00000001"
SHELL_SHUTDOWN_QUIT_ENTRY_PC = 0x0016F8D0
SHELL_SHUTDOWN_MAIN_LOOP_RETURN_PC = 0x0016F8C8
SHELL_SINGLETON_ADDRESS = 0x003672F0
QUIT_GAME_ACTION = "0x3CF57571"
MAX_QUIT_MENU_STEPS = 16
PROFILE_MENU_VTABLE = "0x00343750"


class BiosMissionCaptureError(RuntimeError):
    def __init__(self, message: str, trace: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.trace = trace


class BiosGameSaveCaptureError(RuntimeError):
    def __init__(self, message: str, trace: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.trace = trace


class BiosShellShutdownCaptureError(RuntimeError):
    def __init__(self, message: str, trace: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.trace = trace


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--probe-bios-trace", action="store_true",
                        help="capture the bounded BIOS/IOP census from boot or a savestate")
    parser.add_argument(
        "--probe-bios-phase",
        choices=("title", "title-actions", *STATEFILE_BIOS_PHASES[1:], "mission", "movie"),
        help=(
            "capture a bounded BIOS/IOP phase after a title or observed "
            "profile-menu action, control save/load, a pointer-driven pause "
            "Quit confirmation, clean-boot mission load, or complete native movie I/O"
        ),
    )
    parser.add_argument(
        "--bios-title-actions",
        help="comma-separated native actions for --probe-bios-phase title-actions",
    )
    parser.add_argument("--bios-trace-output", type=Path,
                        help="write --probe-bios-trace JSON to this scratch path")


def validate_arguments(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.bios_trace_output is not None and not (
        args.probe_bios_trace or args.probe_bios_phase
    ):
        parser.error("--bios-trace-output requires a BIOS trace probe")
    if args.probe_bios_trace and args.probe_bios_phase is not None:
        parser.error("choose either --probe-bios-trace or --probe-bios-phase")
    title_actions = getattr(args, "bios_title_actions", None)
    if args.probe_bios_phase == "title-actions":
        if not isinstance(title_actions, str) or not title_actions:
            parser.error("--probe-bios-phase title-actions requires --bios-title-actions")
        invalid = [action for action in title_actions.split(",") if action not in TITLE_MENU_ACTIONS]
        if invalid:
            parser.error(f"unsupported --bios-title-actions value(s): {','.join(invalid)}")
    elif title_actions is not None:
        parser.error("--bios-title-actions requires --probe-bios-phase title-actions")
    if args.probe_bios_phase in STATEFILE_BIOS_PHASES and args.statefile is None:
        parser.error("--probe-bios-phase requires --statefile")
    if args.probe_bios_phase in ("game-save", "game-load") \
            and getattr(args, "memory_card_source", None) is None:
        parser.error(
            f"--probe-bios-phase {args.probe_bios_phase} requires --memory-card-source"
        )
    if args.probe_bios_phase == "mission":
        if args.statefile is not None:
            parser.error("--probe-bios-phase mission requires a clean boot without --statefile")
        if getattr(args, "memory_card_source", None) is None:
            parser.error("--probe-bios-phase mission requires --memory-card-source")
        if getattr(args, "probe_load_timing", None):
            parser.error("--probe-bios-phase mission cannot combine with --probe-load-timing")
    if args.probe_bios_phase == "movie":
        if args.statefile is not None:
            parser.error("--probe-bios-phase movie requires a clean boot without --statefile")
        if not getattr(args, "probe_native_movie_reads", False):
            parser.error("--probe-bios-phase movie requires --probe-native-movie-reads")


def bios_trace_is_verified(trace: object) -> bool:
    """Accept one complete, bounded, ordered trace from a clean control boot."""
    if not isinstance(trace, dict) \
            or trace.get("schema") != BIOS_TRACE_SCHEMA \
            or trace.get("enabled") is not True:
        return False
    capacity = trace.get("capacity")
    overflow = trace.get("overflow")
    events = trace.get("events")
    if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity <= 0 \
            or not isinstance(overflow, int) or isinstance(overflow, bool) or overflow != 0 \
            or not isinstance(events, list) or not events or len(events) > capacity:
        return False

    bios_entry_calls = 0
    bios_entry_identities: dict[tuple[int, str], int] = {}
    # Result semantics are identity-level ABI facts, independent of event coalescing.
    bios_result_expectations: dict[tuple[int, str], bool] = {}
    return_identities: dict[tuple[int, str], int] = {}
    return_calls = 0
    oracle_import_calls = 0
    oracle_import_identities: dict[tuple[object, ...], int] = {}
    oracle_return_calls = 0
    oracle_return_identities: dict[tuple[object, ...], int] = {}
    for expected_sequence, event in enumerate(events, start=1):
        if not isinstance(event, dict) \
                or event.get("sequence") != expected_sequence \
                or not isinstance(event.get("kind"), str) \
                or event["kind"] not in BIOS_EVENT_KINDS:
            return False
        calls = event.get("calls", 1)
        if isinstance(calls, bool) or not isinstance(calls, int) or calls <= 0:
            return False
        if event["kind"] in {"ee_syscall", "import"} \
                and not _service_event_is_verified(event, calls):
            return False
        if event["kind"] == "ee_syscall" \
                and event.get("outcome") == "bios" \
                and event.get("return_expected") is True:
            bios_entry_calls += calls
            identity = (event["number"], event["name"])
            bios_entry_identities[identity] = bios_entry_identities.get(identity, 0) + calls
            result_expected = event["result_expected"]
            if identity in bios_result_expectations \
                    and bios_result_expectations[identity] != result_expected:
                return False
            bios_result_expectations[identity] = result_expected
        if event["kind"] == "ee_syscall_return":
            if not _syscall_return_event_is_verified(event, calls):
                return False
            return_calls += calls
            identity = (event["number"], event["name"])
            return_identities[identity] = return_identities.get(identity, 0) + calls
            if identity not in bios_entry_identities \
                    or event["result_expected"] != bios_result_expectations[identity]:
                return False
        if event["kind"] == "import" and event.get("outcome") == "oracle":
            identity = _iop_oracle_pair_identity(event)
            oracle_import_calls += calls
            oracle_import_identities[identity] = (
                oracle_import_identities.get(identity, 0) + calls
            )
        if event["kind"] == "iop_import_return":
            if not _iop_import_return_event_is_verified(event, calls):
                return False
            identity = _iop_oracle_pair_identity(event)
            if identity not in oracle_import_identities:
                return False
            oracle_return_calls += calls
            oracle_return_identities[identity] = (
                oracle_return_identities.get(identity, 0) + calls
            )
            if oracle_return_identities[identity] > oracle_import_identities[identity]:
                return False
    if any(calls > bios_entry_identities[identity]
           for identity, calls in return_identities.items()):
        return False
    return bool(
        _syscall_pairing_is_verified(
            trace.get("ee_syscall_pairing"), bios_entry_calls, return_calls
        )
        and _iop_import_pairing_is_verified(
            trace.get("iop_import_pairing"), oracle_import_calls, oracle_return_calls
        )
    )


def _service_event_is_verified(event: dict[str, object], calls: int) -> bool:
    arguments = event.get("first_arguments")
    outcome = event.get("outcome")
    result_valid = event.get("result_valid")
    result_expected = event.get("result_expected")
    return_expected = event.get("return_expected")
    if not isinstance(arguments, list) or len(arguments) != 4 \
            or any(not _is_u32(argument) for argument in arguments) \
            or not isinstance(outcome, str) \
            or not isinstance(result_valid, bool) \
            or (event["kind"] == "ee_syscall" and not isinstance(result_expected, bool)):
        return False
    if not event_result_is_verified(
        event, result_valid, event["kind"] == "ee_syscall", calls
    ):
        return False

    if event["kind"] == "ee_syscall":
        number = event.get("number")
        name = event.get("name")
        return bool(
            isinstance(number, int)
            and not isinstance(number, bool)
            and 0 <= number <= 0xff
            and isinstance(name, str)
            and name
            and isinstance(return_expected, bool)
            and outcome in {"bios", "direct"}
            and (outcome != "bios" or not result_valid)
            and (
                outcome != "direct"
                or (return_expected and result_valid == result_expected)
            )
            and (return_expected or (not result_expected and not result_valid))
        )

    library = event.get("library")
    ordinal = event.get("ordinal")
    function = event.get("function")
    hle_available = event.get("hle_available")
    debug_available = event.get("debug_available")
    return bool(
        isinstance(library, str)
        and library
        and isinstance(ordinal, int)
        and not isinstance(ordinal, bool)
        and 0 <= ordinal <= 0xffff
        and isinstance(function, str)
        and function
        and isinstance(hle_available, bool)
        and isinstance(debug_available, bool)
        and outcome in {"hle", "oracle"}
        and result_valid == (outcome == "hle")
        and (outcome != "hle" or (hle_available and bool(function)))
        and (
            outcome != "oracle"
            or (
                _is_u32(event.get("first_stack_pointer"))
                and _is_u32(event.get("first_resume_pc"))
            )
        )
    )


def _is_u32(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value < (1 << 32)


def _syscall_return_event_is_verified(event: dict[str, object], calls: int) -> bool:
    number = event.get("number")
    name = event.get("name")
    result_expected = event.get("result_expected")
    result_valid = event.get("result_valid")
    return bool(
        isinstance(number, int)
        and not isinstance(number, bool)
        and 0 <= number <= 0xff
        and isinstance(name, str)
        and name
        and isinstance(result_expected, bool)
        and isinstance(result_valid, bool)
        and (not result_valid or result_expected)
        and event_result_is_verified(event, result_valid, True, calls)
        and _is_u32(event.get("first_stack_pointer"))
        and _is_u32(event.get("first_resume_pc"))
    )


def _iop_import_identity(event: dict[str, object]) -> tuple[object, ...]:
    return (
        event.get("library"),
        event.get("ordinal"),
        event.get("function"),
        event.get("hle_available"),
        event.get("debug_available"),
    )


def _iop_oracle_pair_identity(event: dict[str, object]) -> tuple[object, ...]:
    return _iop_import_identity(event) + (
        event.get("first_stack_pointer"),
        event.get("first_resume_pc"),
    )


def _iop_import_return_event_is_verified(
    event: dict[str, object], calls: int
) -> bool:
    library, ordinal, function, hle_available, debug_available = (
        _iop_import_identity(event)
    )
    return bool(
        isinstance(library, str)
        and library
        and isinstance(ordinal, int)
        and not isinstance(ordinal, bool)
        and 0 <= ordinal <= 0xffff
        and isinstance(function, str)
        and function
        and isinstance(hle_available, bool)
        and isinstance(debug_available, bool)
        and event.get("result_valid") is True
        and event_result_is_verified(event, True, False, calls)
        and _is_u32(event.get("first_stack_pointer"))
        and _is_u32(event.get("first_resume_pc"))
    )


def _syscall_pairing_is_verified(
    pairing: object, bios_entry_calls: int, return_calls: int
) -> bool:
    if not isinstance(pairing, dict):
        return False
    values = {
        key: pairing.get(key)
        for key in ("entries", "returns", "pending", "sequence_errors", "overflow")
    }
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
           for value in values.values()):
        return False
    return bool(
        values["sequence_errors"] == 0
        and values["overflow"] == 0
        and values["entries"] == bios_entry_calls
        and values["returns"] == return_calls
        and values["pending"] == bios_entry_calls - return_calls
    )


def _iop_import_pairing_is_verified(
    pairing: object, oracle_entry_calls: int, return_calls: int
) -> bool:
    if not isinstance(pairing, dict):
        return False
    values = {
        key: pairing.get(key)
        for key in ("entries", "returns", "pending", "overflow")
    }
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
           for value in values.values()):
        return False
    return bool(
        values["overflow"] == 0
        and values["entries"] == oracle_entry_calls
        and values["returns"] == return_calls
        and values["pending"] == oracle_entry_calls - return_calls
    )


def bios_trace_failure_detail(trace: object) -> str:
    if not isinstance(trace, dict):
        return f"response is not an object ({type(trace).__name__})"
    events = trace.get("events")
    event_count = len(events) if isinstance(events, list) else "invalid"
    detail = (
        f"schema={trace.get('schema')!r} enabled={trace.get('enabled')!r} "
        f"events={event_count} overflow={trace.get('overflow')!r}"
    )
    pairing = trace.get("ee_syscall_pairing")
    if isinstance(pairing, dict):
        detail += (
            f" syscall_entries={pairing.get('entries')!r}"
            f" syscall_returns={pairing.get('returns')!r}"
            f" syscall_pending={pairing.get('pending')!r}"
            f" syscall_sequence_errors={pairing.get('sequence_errors')!r}"
            f" syscall_overflow={pairing.get('overflow')!r}"
        )
    iop_pairing = trace.get("iop_import_pairing")
    if isinstance(iop_pairing, dict):
        detail += (
            f" iop_import_entries={iop_pairing.get('entries')!r}"
            f" iop_import_returns={iop_pairing.get('returns')!r}"
            f" iop_import_pending={iop_pairing.get('pending')!r}"
            f" iop_import_overflow={iop_pairing.get('overflow')!r}"
        )
    boundary = trace.get("mission_boundary")
    if isinstance(boundary, dict):
        detail += (
            f" mission_complete={boundary.get('complete')!r}"
            f" mission_entry={boundary.get('entry') is not None}"
            f" mission_return={boundary.get('return') is not None}"
            f" mission_load_error={boundary.get('load_error')!r}"
            f" mission_load_progress={boundary.get('load_progress')!r}"
            f" mission_sequence_errors={boundary.get('sequence_errors')!r}"
        )
    shell_boundary = trace.get("shell_shutdown_boundary")
    if isinstance(shell_boundary, dict):
        detail += (
            f" shell_shutdown_complete={shell_boundary.get('complete')!r}"
            f" shell_shutdown_quit_entry={shell_boundary.get('quit_entry') is not None}"
            f" shell_shutdown_main_loop_return={shell_boundary.get('main_loop_return') is not None}"
            f" shell_shutdown_quit_bit={shell_boundary.get('quit_bit_observed')!r}"
            f" shell_shutdown_sequence_errors={shell_boundary.get('sequence_errors')!r}"
        )
    game_load_boundary = trace.get("game_load_boundary")
    if isinstance(game_load_boundary, dict):
        detail += (
            f" game_load_complete={game_load_boundary.get('complete')!r}"
            f" game_load_pacify_calls={game_load_boundary.get('pacify_process_calls')!r}"
            f" game_load_entry={game_load_boundary.get('entry') is not None}"
            f" game_load_return={game_load_boundary.get('return') is not None}"
            f" game_load_sequence_errors={game_load_boundary.get('sequence_errors')!r}"
        )
    return detail


def mission_boundary_is_verified(trace: object) -> bool:
    if not bios_trace_is_verified(trace):
        return False
    assert isinstance(trace, dict)
    boundary = trace.get("mission_boundary")
    if not isinstance(boundary, dict) \
            or boundary.get("complete") is not True \
            or boundary.get("sequence_errors") != 0 \
            or boundary.get("entry_pc") != MISSION_TRACE_ENTRY_PC \
            or boundary.get("return_pc") != MISSION_TRACE_RETURN_PC:
        return False
    entry = boundary.get("entry")
    returned = boundary.get("return")
    return bool(
        isinstance(entry, dict)
        and isinstance(returned, dict)
        and entry.get("pc") == MISSION_TRACE_ENTRY_PC
        and returned.get("pc") == MISSION_TRACE_RETURN_PC
    )


def game_save_boundary_is_verified(trace: object) -> bool:
    if not bios_trace_is_verified(trace) or not isinstance(trace, dict):
        return False
    boundary = trace.get("game_save_boundary")
    if not isinstance(boundary, dict) or any((
        boundary.get("entry_pc") != GAME_SAVE_TRACE_ENTRY_PC,
        boundary.get("return_pc") != GAME_SAVE_TRACE_RETURN_PC,
        boundary.get("pacify_process_pc") != GAME_SAVE_PACIFY_PROCESS_PC,
        isinstance(boundary.get("pacify_process_calls"), bool),
        not isinstance(boundary.get("pacify_process_calls"), int),
        boundary.get("pacify_process_calls", 0) <= 0,
        boundary.get("complete") is not True,
        boundary.get("succeeded") is not True,
        boundary.get("result") != 0,
        boundary.get("sequence_errors") != 0,
    )):
        return False
    entry = boundary.get("entry")
    returned = boundary.get("return")
    if not isinstance(entry, dict) or not isinstance(returned, dict) or any((
        entry.get("pc") != GAME_SAVE_TRACE_ENTRY_PC,
        returned.get("pc") != GAME_SAVE_TRACE_RETURN_PC,
    )):
        return False
    for field in ("ee_cycle", "iop_cycle", "frame", "host_time_ns"):
        if any((
            isinstance(entry.get(field), bool),
            not isinstance(entry.get(field), int),
            isinstance(returned.get(field), bool),
            not isinstance(returned.get(field), int),
        )):
            return False
    return bool(
        returned["ee_cycle"] > entry["ee_cycle"]
        and returned["iop_cycle"] >= entry["iop_cycle"]
        and returned["frame"] >= entry["frame"]
        and returned["host_time_ns"] > entry["host_time_ns"]
    )


def capture_bios_trace(port: int, at_guest_boundary: bool = True) -> dict[str, object]:
    route = "/bios/trace/capture-at-guest-boundary" if at_guest_boundary else "/bios/trace/capture"
    status, body = request_bytes(port, "POST", route, {}, timeout=7.0)
    if status != 200:
        raise RuntimeError(f"BIOS trace capture returned HTTP {status}")
    trace = json.loads(body)
    if not bios_trace_is_verified(trace):
        raise RuntimeError(
            "complete BIOS trace was not observed: "
            f"{bios_trace_failure_detail(trace)}"
        )
    return trace


def start_bios_trace(port: int) -> None:
    status, body = request_bytes(port, "POST", "/bios/trace/start", {})
    if status != 200:
        raise RuntimeError(
            f"BIOS trace start returned HTTP {status}: {body.decode(errors='replace').strip()}"
        )


def start_bios_mission_phase(port: int) -> None:
    status, body = request_bytes(port, "POST", "/bios/trace/start-mission", {})
    if status != 200:
        raise RuntimeError(
            "BIOS mission trace start returned HTTP "
            f"{status}: {body.decode(errors='replace').strip()}"
        )


def start_bios_game_save_phase(port: int) -> None:
    status, body = request_bytes(port, "POST", "/bios/trace/start-game-save", {})
    if status != 200:
        raise RuntimeError(
            "BIOS game-save trace start returned HTTP "
            f"{status}: {body.decode(errors='replace').strip()}"
        )


def capture_bios_mission_boundary(port: int) -> dict[str, object]:
    status, body = request_bytes(port, "POST", "/bios/trace/capture-mission", {}, timeout=122.0)
    if status != 200:
        try:
            diagnostic = json.loads(body)
        except json.JSONDecodeError:
            diagnostic = None
        debug_status, debug, debug_detail = request_json(port, "GET", "/debug", {})
        if debug_status == 200 and debug is not None:
            debug_suffix = f" debug={debug}"
        else:
            debug_suffix = f" debug_unavailable={debug_detail}"
        raise BiosMissionCaptureError(
            f"BIOS mission trace capture returned HTTP {status}: "
            f"{bios_trace_failure_detail(diagnostic)}{debug_suffix}",
            diagnostic if isinstance(diagnostic, dict) else None,
        )
    trace = json.loads(body)
    if not mission_boundary_is_verified(trace):
        raise BiosMissionCaptureError(
            "complete grounded mission boundary was not observed: "
            f"{bios_trace_failure_detail(trace)}",
            trace if isinstance(trace, dict) else None,
        )
    assert isinstance(trace, dict)
    return trace


def capture_bios_game_save_boundary(port: int) -> dict[str, object]:
    status, body = request_bytes(port, "POST", "/bios/trace/capture-game-save", {}, timeout=22.0)
    try:
        trace = json.loads(body)
    except json.JSONDecodeError:
        trace = None
    if status != 200:
        raise BiosGameSaveCaptureError(
            f"BIOS game-save trace capture returned HTTP {status}: "
            f"{bios_trace_failure_detail(trace)}",
            trace if isinstance(trace, dict) else None,
        )
    if not game_save_boundary_is_verified(trace):
        raise BiosGameSaveCaptureError(
            "complete grounded game-save boundary was not observed: "
            f"{bios_trace_failure_detail(trace)}",
            trace if isinstance(trace, dict) else None,
        )
    assert isinstance(trace, dict)
    return trace


def shell_shutdown_boundary_is_verified(trace: object) -> bool:
    if not bios_trace_is_verified(trace) or not isinstance(trace, dict):
        return False
    boundary = trace.get("shell_shutdown_boundary")
    if not isinstance(boundary, dict) or any((
        boundary.get("complete") is not True,
        boundary.get("quit_bit_observed") is not True,
        boundary.get("sequence_errors") != 0,
    )):
        return False
    entry = boundary.get("quit_entry")
    returned = boundary.get("main_loop_return")
    if not isinstance(entry, dict) or not isinstance(returned, dict) or any((
        entry.get("pc") != SHELL_SHUTDOWN_QUIT_ENTRY_PC,
        returned.get("pc") != SHELL_SHUTDOWN_MAIN_LOOP_RETURN_PC,
    )):
        return False
    return all(
        isinstance(entry.get(field), int) and not isinstance(entry.get(field), bool)
        and isinstance(returned.get(field), int) and not isinstance(returned.get(field), bool)
        for field in ("ee_cycle", "iop_cycle", "frame", "host_time_ns")
    ) and returned["ee_cycle"] > entry["ee_cycle"] and returned["iop_cycle"] >= entry["iop_cycle"] \
        and returned["frame"] >= entry["frame"] and returned["host_time_ns"] > entry["host_time_ns"]


def movie_boundary_is_verified(trace: object) -> bool:
    if not bios_trace_is_verified(trace) or not isinstance(trace, dict):
        return False
    return trace.get("movie_boundary") == {
        "path": "MOVIES/EALOGO.PSS",
        "complete": True,
    }


def capture_bios_movie_boundary(port: int) -> dict[str, object]:
    status, body = request_bytes(port, "POST", "/bios/trace/capture-movie", {}, timeout=32.0)
    try:
        trace = json.loads(body)
    except json.JSONDecodeError:
        trace = None
    if status != 200:
        raise RuntimeError(
            f"BIOS movie trace capture returned HTTP {status}: {bios_trace_failure_detail(trace)}"
        )
    if not movie_boundary_is_verified(trace):
        raise RuntimeError(
            "complete grounded native movie boundary was not observed: "
            f"{bios_trace_failure_detail(trace)}"
        )
    assert isinstance(trace, dict)
    return trace


def start_bios_shell_shutdown_phase(port: int) -> None:
    status, body = request_bytes(port, "POST", "/bios/trace/start-shell-shutdown", {})
    if status != 200:
        shell = read_guest_word(port, SHELL_SINGLETON_ADDRESS)
        first_word = read_guest_word(port, shell) if shell else None
        raise RuntimeError(
            "BIOS shell-shutdown trace start returned HTTP "
            f"{status}: {body.decode(errors='replace').strip()}; "
            f"shell_singleton=0x{shell:08x}, shell_first_word={None if first_word is None else f'0x{first_word:08x}'}"
        )


def capture_bios_shell_shutdown_boundary(port: int) -> dict[str, object]:
    status, body = request_bytes(port, "POST", "/bios/trace/capture-shell-shutdown", {}, timeout=22.0)
    try:
        trace = json.loads(body)
    except json.JSONDecodeError:
        trace = None
    if status != 200:
        raise BiosShellShutdownCaptureError(
            f"BIOS shell-shutdown trace capture returned HTTP {status}: "
            f"{bios_trace_failure_detail(trace)}",
            trace if isinstance(trace, dict) else None,
        )
    if not shell_shutdown_boundary_is_verified(trace):
        raise BiosShellShutdownCaptureError(
            "complete grounded shell-shutdown boundary was not observed: "
            f"{bios_trace_failure_detail(trace)}",
            trace if isinstance(trace, dict) else None,
        )
    assert isinstance(trace, dict)
    return trace


def prepare_bios_trace_for_native_stream(port: int, enabled: bool) -> None:
    if enabled:
        start_bios_trace(port)


def _select_game_save_slot(port: int, deadline: float) -> dict[str, object]:
    """Use GSaveGameMenu's grounded ActivateFocused action, not pad emulation."""
    state_status, state, state_detail = menu_state(port)
    if state_status != 200 or state is None:
        raise RuntimeError(
            "game-save source menu is unavailable: "
            f"HTTP {state_status}: {state_detail}"
        )
    if state.get("focus_object") == "0x00000000":
        pointer_focus = focus_dispatched_menu_pointer(port, deadline)
        state["pointer_focus"] = pointer_focus
        state["pointer_activation"] = activate_focused_dispatched_menu_pointer(port, deadline)
        return {"before": state, "action": "pointer-activate"}
    status, response, detail = menu_action(port, "activate")
    if status == 202 and response is not None:
        # Callback-registry actions complete at the game's ordinary input-dispatch
        # return. Synchronous modal actions use the EE call shuttle instead.
        action_id = response.get("dispatch_action_id")
        if isinstance(action_id, int) and not isinstance(action_id, bool) and action_id > 0:
            completion = await_dispatched_menu_action(port, deadline, action_id)
            return {
                "before": state,
                "action": "activate",
                "response": response,
                "dispatch": completion,
            }
        call_id = response.get("deferred_call_id")
        if not isinstance(call_id, int) or call_id <= 0:
            raise RuntimeError(f"game-save activation returned invalid call: {detail}")
        await_deferred_call(port, deadline, call_id, "BIOS phase game-save activate")
        return {"before": state, "action": "activate", "deferred_call_id": call_id}
    if status == 200 and response is not None:
        return {"before": state, "action": "activate", "response": response}
    raise RuntimeError(f"game-save activation failed: HTTP {status}: {detail}")


def _focus_menu_action(
    port: int,
    deadline: float,
    target_action: str,
    context: str,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    observations: list[dict[str, object]] = []
    seen_focuses: set[tuple[object, object, object]] = set()
    for step in range(MAX_QUIT_MENU_STEPS):
        _, candidate = _await_settled_menu_state(
            port, deadline, f"{context} discovery at step {step}"
        )
        observations.append(candidate)
        if candidate.get("focused_item_action") == target_action:
            return candidate, observations
        focus_identity = tuple(
            candidate.get(field)
            for field in ("focus_handle", "focus_object", "focused_item_action")
        )
        if focus_identity in seen_focuses:
            raise RuntimeError(
                f"{context} repeated a non-target focus: {candidate}; "
                f"observed={observations}"
            )
        seen_focuses.add(focus_identity)
        completion = _complete_menu_action(
            port, deadline, "down", f"{context} down at step {step}"
        )
        await_following_menu_input_dispatch(
            port, deadline, candidate.get("menu"), completion
        )
    raise RuntimeError(
        f"{context} did not focus action {target_action} within "
        f"{MAX_QUIT_MENU_STEPS} observed actions: {observations}"
    )


def _prepare_empty_game_save_slot(port: int, deadline: float) -> dict[str, object]:
    pause = probe_gameplay_pause_menu(port, deadline)
    save_item, pause_navigation = _focus_menu_action(
        port, deadline, LOAD_MENU_ACTION, "BIOS phase game-save pause Save"
    )
    activation = _complete_menu_action(
        port, deadline, "activate", "BIOS phase game-save pause Save activation"
    )
    next_menu_owner, next_menu_dispatch = await_different_menu_input_dispatch(
        port, deadline, save_item.get("menu"), activation, GAME_SAVE_MENU_VTABLE
    )
    status, save_menu = _await_settled_menu_state(
        port, deadline, "BIOS phase game-save Save menu readiness"
    )
    if status != 200 or save_menu.get("menu_vtable") != GAME_SAVE_MENU_VTABLE:
        raise RuntimeError(
            "BIOS phase game-save did not reach the grounded GSaveGameMenu: "
            f"status={status}, state={save_menu}"
        )
    empty_slot, slot_navigation = _focus_menu_action(
        port, deadline, EMPTY_GAME_SAVE_SLOT_ACTION,
        "BIOS phase game-save empty slot",
    )
    return {
        "pause": pause,
        "save_item": save_item,
        "pause_navigation": pause_navigation,
        "save_activation": activation,
        "save_menu_dispatch_owner": next_menu_owner,
        "save_menu_dispatch": next_menu_dispatch,
        "save_menu": save_menu,
        "empty_slot": empty_slot,
        "slot_navigation": slot_navigation,
    }


def _focus_quit_game(port: int, deadline: float) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Navigate only through observed menu actions until the live QuitGame item is focused."""
    return _focus_menu_action(
        port, deadline, QUIT_GAME_ACTION, "BIOS phase shutdown QuitGame"
    )


def _capture_pointer_shutdown_phase(
    port: int, deadline: float, pause: dict[str, object], selections: list[dict[str, int]]
) -> tuple[dict[str, object], str, str]:
    quit_menu, quit_menu_observations = _focus_pause_selection(
        port, deadline, selections, LOAD_MENU_ACTION, PAUSE_QUIT_TEXT)
    quit_menu_activation = activate_focused_dispatched_menu_pointer(port, deadline)
    quit_menu_status, quit_menu_state = _await_settled_menu_state(
        port, deadline, "BIOS phase shutdown Quit menu transition")
    quit_menu_parent = _menu_parent(port, quit_menu_state)
    quit_menu_parent_action_handler = _menu_parent_action_handler(port, quit_menu_parent)
    confirmation_selections = _pause_selection_rectangles(port)
    try:
        confirmation, confirmation_observations = _focus_pause_selection(
            port, deadline, confirmation_selections, None, "Yes")
    except RuntimeError as error:
        raise RuntimeError(
            f"{error}; quit_menu_state={{'status': {quit_menu_status}, 'state': {quit_menu_state}}}") from error
    start_bios_shell_shutdown_phase(port)
    activation = activate_focused_dispatched_menu_pointer(port, deadline)
    fields = {
        "pause_menu": pause,
        "selected_rectangles": selections,
        "quit_menu": quit_menu,
        "quit_menu_observations": quit_menu_observations,
        "quit_menu_activation": quit_menu_activation,
        "quit_menu_state": {"status": quit_menu_status, "state": quit_menu_state},
        "quit_menu_parent_action_handler": quit_menu_parent_action_handler,
        "quit_confirmation_rectangles": confirmation_selections,
        "quit_confirmation": confirmation,
        "quit_confirmation_observations": confirmation_observations,
        "quit_confirmation_activation": activation,
    }
    try:
        trace = capture_bios_shell_shutdown_boundary(port)
    except BiosShellShutdownCaptureError as error:
        if error.trace is not None:
            error.trace.update(fields)
        raise
    trace.update(fields)
    return trace, "mission_to_pause_quit_confirmation", "pad_start_then_quit_then_confirmation"


def run_bios_phase(
    port: int,
    deadline: float,
    phase: str,
    statefile: Path | None,
    state_path: Path,
    title_actions: tuple[str, ...] = (),
) -> tuple[dict[str, object], str, str]:
    if phase == "movie":
        return (
            capture_bios_movie_boundary(port),
            "clean_boot_native_movie",
            "ealogo_native_open_to_ioman_close",
        )
    if phase == "mission":
        await_native_stream_reads(
            port, deadline, "native MENU01 readiness before the BIOS mission boundary"
        )
        start_bios_mission_phase(port)
        transition = probe_marine_m1_transition(
            port, deadline, state_path.parent, require_native_assets=True
        )
        try:
            trace = capture_bios_mission_boundary(port)
        except BiosMissionCaptureError as error:
            if error.trace is not None:
                error.trace["mission_transition_proof"] = transition
            raise
        trace["mission_transition_proof"] = transition
        return trace, "clean_boot_to_mission", "shell_set_next_level"
    if phase == "title":
        title_menu = _activate_title_menu(port, deadline, start_bios_trace)
        trace = capture_bios_trace(port, at_guest_boundary=False)
        trace["title_menu_after_action"] = title_menu
        return trace, "zono_splash_to_title_menu_action", "start_then_title_activate"
    if phase == "title-actions":
        if not title_actions:
            raise ValueError("title-actions phase requires at least one action")
        _reach_title_menu(port, deadline)
        states: list[dict[str, object]] = []
        for action in title_actions:
            _, before = _await_settled_menu_state(
                port, deadline, f"BIOS phase title pre-{action} menu discovery"
            )
            _complete_menu_action(port, deadline, action, f"BIOS phase title {action}")
            if action == "activate":
                status, title_menu = _await_menu_transition(
                    port, deadline, before, f"BIOS phase title post-{action} menu transition"
                )
            else:
                status, title_menu = _await_settled_menu_state(
                    port, deadline, f"BIOS phase title post-{action} menu discovery"
                )
            states.append({"action": action, "status": status, "state": title_menu})
        start_bios_trace(port)
        trace = capture_bios_trace(port, at_guest_boundary=False)
        trace["title_menu_actions"] = states
        return trace, "zono_splash_to_title_menu_actions", ",".join(title_actions)
    if phase == "title-down":
        _reach_title_menu(port, deadline)
        start_bios_trace(port)
        _complete_menu_action(port, deadline, "down", "BIOS phase title down")
        status, title_menu = _await_settled_menu_state(
            port, deadline, "BIOS phase title post-down menu discovery"
        )
        trace = capture_bios_trace(port, at_guest_boundary=False)
        trace["title_menu_after_down"] = {"status": status, "state": title_menu}
        return trace, "zono_splash_to_title_menu_direction", "start_then_title_down"
    if phase == "title-down-activate":
        down_menu, title_menu = _activate_title_menu_after_down(
            port, deadline, start_bios_trace
        )
        trace = capture_bios_trace(port, at_guest_boundary=False)
        trace["title_menu_after_down"] = down_menu
        trace["title_menu_after_down_activation"] = title_menu
        return trace, "zono_splash_to_title_menu_transition", "start_then_title_down_activate"
    if phase == "title-profile":
        title_menu = _activate_title_menu(port, deadline, start_bios_trace)
        profile_state = title_menu["state"]
        if title_menu["status"] != 200 or not isinstance(profile_state, dict) \
                or profile_state.get("menu_vtable") != PROFILE_MENU_VTABLE:
            raise RuntimeError(
                "BIOS phase title did not settle at the grounded GProfileMenu before activation: "
                f"{title_menu}"
            )
        _complete_menu_action(port, deadline, "activate", "BIOS phase profile activate")
        status, next_menu = _await_menu_transition(
            port, deadline, profile_state, "BIOS phase profile post-action menu transition"
        )
        trace = capture_bios_trace(port, at_guest_boundary=False)
        trace["title_menu_after_action"] = title_menu
        trace["profile_menu_after_action"] = {"status": status, "state": next_menu}
        return trace, "zono_splash_to_profile_menu_action", "start_then_title_and_profile_activate"
    if phase == "menu":
        start_bios_trace(port)
        _complete_menu_action(port, deadline, "down", "BIOS phase menu down")
        return capture_bios_trace(port), "statefile_to_menu", "menu_down"
    if phase == "save-load":
        status, response, detail = request_json(
            port, "POST", "/state/save", {"path": str(state_path)}
        )
        if status != 200 or response is None or response.get("saved") is not True:
            raise RuntimeError(f"BIOS phase state save failed: HTTP {status}: {detail}")
        start_bios_trace(port)
        status, response, detail = request_json(
            port, "POST", "/state/load", {"path": str(statefile)}
        )
        if status != 200 or response is None or response.get("loaded") is not True:
            raise RuntimeError(f"BIOS phase state load failed: HTTP {status}: {detail}")
        _complete_menu_action(port, deadline, "down", "BIOS phase save-load menu down")
        return (
            capture_bios_trace(port, at_guest_boundary=False),
            "save_load_to_menu_action",
            "state_save_load_then_menu_down",
        )
    if phase == "game-save":
        preparation = _prepare_empty_game_save_slot(port, deadline)
        start_bios_game_save_phase(port)
        selection = _select_game_save_slot(port, deadline)
        try:
            trace = capture_bios_game_save_boundary(port)
        except BiosGameSaveCaptureError as error:
            if error.trace is not None:
                error.trace["game_save_menu_selection"] = selection
            raise
        trace["game_save_menu_selection"] = selection
        trace["game_save_menu_preparation"] = preparation
        return trace, "gameplay_to_game_save", "pause_save_empty_slot_to_cprofile_save_game"
    if phase == "game-load":
        return run_game_load_phase(port, deadline)
    if phase == "shutdown":
        pause = probe_gameplay_pause_menu(port, deadline)
        selections = _pause_selection_rectangles(port)
        try:
            candidate, navigation = _focus_quit_game(port, deadline)
        except RuntimeError as error:
            raise RuntimeError(f"{error}; selected_rectangles={selections}") from error
        start_bios_shell_shutdown_phase(port)
        _complete_menu_action(port, deadline, "activate", "BIOS phase shutdown QuitGame activation")
        try:
            trace = capture_bios_shell_shutdown_boundary(port)
        except BiosShellShutdownCaptureError as error:
            if error.trace is not None:
                error.trace["pause_menu"] = pause
                error.trace["quit_game_menu"] = candidate
                error.trace["quit_game_navigation"] = navigation
                error.trace["selected_rectangles"] = selections
            raise
        trace["pause_menu"] = pause
        trace["quit_game_menu"] = candidate
        trace["quit_game_navigation"] = navigation
        trace["selected_rectangles"] = selections
        return trace, "mission_to_shell_shutdown", "pad_start_then_quit_game"
    if phase == "shutdown-pointer":
        pause = probe_gameplay_pause_menu(port, deadline)
        selections = _pause_selection_rectangles(port)
        return _capture_pointer_shutdown_phase(port, deadline, pause, selections)
    raise ValueError(f"unsupported BIOS phase: {phase}")


def capture_bios_trace_if_requested(
    enabled: bool, port: int, probe_error: str | None
) -> tuple[dict[str, object] | None, str | None]:
    if not enabled or probe_error is not None:
        return None, None
    try:
        return capture_bios_trace(port), None
    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
        return None, str(error)


def run_requested_bios_probe(
    args: argparse.Namespace, port: int, deadline: float, log_dir: Path
) -> tuple[dict[str, object] | None, str | None, str | None, str | None]:
    if args.probe_bios_trace:
        trace, error = capture_bios_trace_if_requested(True, port, None)
        return trace, None, None, error
    if args.probe_bios_phase is not None:
        try:
            trace, phase, operation = run_bios_phase(
                port,
                deadline,
                args.probe_bios_phase,
                args.statefile,
                log_dir.parent / "bios-phase-state.p2s",
                tuple(getattr(args, "bios_title_actions", "").split(","))
                if getattr(args, "bios_title_actions", None) else (),
            )
            return trace, phase, operation, None
        except BiosMissionCaptureError as error:
            return (
                error.trace,
                "clean_boot_to_mission",
                "shell_set_next_level",
                str(error),
            )
        except BiosShellShutdownCaptureError as error:
            return (
                error.trace,
                "mission_to_pause_quit_confirmation"
                if args.probe_bios_phase == "shutdown-pointer"
                else "mission_to_shell_shutdown",
                "pad_start_then_quit_then_confirmation"
                if args.probe_bios_phase == "shutdown-pointer"
                else "pad_start_then_quit_game",
                str(error),
            )
        except BiosGameSaveCaptureError as error:
            return (
                error.trace,
                "statefile_to_game_save",
                "slot_select_to_cprofile_save_game",
                str(error),
            )
        except BiosGameLoadCaptureError as error:
            return (
                error.trace,
                "gameplay_to_game_load",
                "pause_load_slot_confirm_to_cprofile_load_game",
                str(error),
            )
        except (RuntimeError, ValueError, json.JSONDecodeError) as error:
            return None, None, None, str(error)
    return None, None, None, None


def write_bios_trace(
    trace: dict[str, object],
    output: Path,
    control_status: dict[str, object],
    statefile: Path | None,
    phase: str | None = None,
    operation: str | None = None,
) -> None:
    artifact = {
        "phase": phase or ("clean_boot_to_running" if statefile is None else "statefile_to_running"),
        "control_status": control_status,
        "trace": trace,
    }
    if statefile is not None:
        artifact["statefile"] = statefile.name
    if operation is not None:
        artifact["operation"] = operation
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")


def report_bios_trace(
    trace: dict[str, object] | None,
    output: Path | None,
    control_status: dict[str, object],
    log_dir: Path,
    statefile: Path | None,
    probe_error: str | None,
    phase: str | None = None,
    operation: str | None = None,
) -> bool:
    actual_output = output or (log_dir.parent / "bios-trace.json")
    if trace is not None:
        write_bios_trace(trace, actual_output, control_status, statefile, phase, operation)
    if probe_error is not None:
        output_detail = f"; diagnostic output={actual_output}" if trace is not None else ""
        print(
            f"FATAL BIOS trace failed: {probe_error}{output_detail}; see {log_dir}",
            file=sys.stderr,
        )
        return False
    if trace is None:
        detail = "probe did not run"
        print(f"FATAL BIOS trace failed: {detail}; see {log_dir}", file=sys.stderr)
        return False
    print(f"control-test bios-trace output={actual_output}", flush=True)
    return True
