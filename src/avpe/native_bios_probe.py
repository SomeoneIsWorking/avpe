"""Surfaceless BIOS/IOP census polling and proof policy."""

import argparse
import json
import sys
from pathlib import Path

from avpe.control_http import request_bytes, request_json
from avpe.menu_probe import await_deferred_call, menu_action
from avpe.native_asset_probe import await_native_stream_reads
from avpe.native_mission_probe import probe_marine_m1_transition

BIOS_TRACE_SCHEMA = "avpe-bios-trace-v3"
BIOS_EVENT_KINDS = frozenset(
    {
        "ee_syscall",
        "ee_syscall_return",
        "exception",
        "import",
        "interrupt",
        "module",
        "rpc",
        "timer",
    }
)
MISSION_TRACE_ENTRY_PC = 0x0016F910
MISSION_TRACE_RETURN_PC = 0x0016FA4C


class BiosMissionCaptureError(RuntimeError):
    def __init__(self, message: str, trace: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.trace = trace


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--probe-bios-trace", action="store_true",
                        help="capture the bounded BIOS/IOP census from boot or a savestate")
    parser.add_argument(
        "--probe-bios-phase",
        choices=("menu", "save-load", "mission"),
        help="capture a bounded BIOS/IOP phase after a menu action, save/load, or clean-boot mission load",
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
    if args.probe_bios_phase in ("menu", "save-load") and args.statefile is None:
        parser.error("--probe-bios-phase requires --statefile")
    if args.probe_bios_phase == "mission":
        if args.statefile is not None:
            parser.error("--probe-bios-phase mission requires a clean boot without --statefile")
        if getattr(args, "memory_card_source", None) is None:
            parser.error("--probe-bios-phase mission requires --memory-card-source")
        if getattr(args, "probe_load_timing", None):
            parser.error("--probe-bios-phase mission cannot combine with --probe-load-timing")


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
                and not _service_event_is_verified(event):
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
            if not _syscall_return_event_is_verified(event):
                return False
            return_calls += calls
            identity = (event["number"], event["name"])
            return_identities[identity] = return_identities.get(identity, 0) + calls
            if identity not in bios_entry_identities \
                    or event["result_expected"] != bios_result_expectations[identity]:
                return False
    if any(calls > bios_entry_identities[identity]
           for identity, calls in return_identities.items()):
        return False
    return _syscall_pairing_is_verified(
        trace.get("ee_syscall_pairing"), bios_entry_calls, return_calls
    )


def _service_event_is_verified(event: dict[str, object]) -> bool:
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
    if result_valid:
        result = event.get("result")
        if isinstance(result, bool) or not isinstance(result, int) \
                or not -(1 << 31) <= result < (1 << 31):
            return False
    elif "result" in event:
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
        and (hle_available or debug_available)
        and outcome in {"hle", "oracle"}
        and result_valid == (outcome == "hle")
        and (outcome != "hle" or hle_available)
    )


def _is_u32(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value < (1 << 32)


def _syscall_return_event_is_verified(event: dict[str, object]) -> bool:
    number = event.get("number")
    name = event.get("name")
    result_expected = event.get("result_expected")
    result_valid = event.get("result_valid")
    result = event.get("result")
    return bool(
        isinstance(number, int)
        and not isinstance(number, bool)
        and 0 <= number <= 0xff
        and isinstance(name, str)
        and name
        and isinstance(result_expected, bool)
        and isinstance(result_valid, bool)
        and (not result_valid or result_expected)
        and (
            (not result_valid and "result" not in event)
            or (
                result_valid
                and isinstance(result, int)
                and not isinstance(result, bool)
                and -(1 << 31) <= result < (1 << 31)
            )
        )
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


def prepare_bios_trace_for_native_stream(port: int, enabled: bool) -> None:
    if enabled:
        start_bios_trace(port)


def run_bios_phase(
    port: int,
    deadline: float,
    phase: str,
    statefile: Path | None,
    state_path: Path,
) -> tuple[dict[str, object], str, str]:
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
    if phase == "menu":
        start_bios_trace(port)
        status, response, detail = menu_action(port, "down")
        if status == 202 and response is not None:
            call_id = response.get("deferred_call_id")
            if not isinstance(call_id, int) or call_id <= 0:
                raise RuntimeError(f"BIOS phase menu action returned invalid call: {detail}")
            await_deferred_call(port, deadline, call_id, "BIOS phase menu down")
        elif status != 200 or response is None:
            raise RuntimeError(f"BIOS phase menu action failed: HTTP {status}: {detail}")
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
        return capture_bios_trace(port), "save_load_to_running", "state_save_then_load"
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
            )
            return trace, phase, operation, None
        except BiosMissionCaptureError as error:
            return (
                error.trace,
                "clean_boot_to_mission",
                "shell_set_next_level",
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
