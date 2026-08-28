"""Surfaceless BIOS/IOP census polling and proof policy."""

import argparse
import json
import sys
from pathlib import Path

from avpe.control_http import request_bytes, request_json
from avpe.menu_probe import await_deferred_call, menu_action

BIOS_TRACE_SCHEMA = "avpe-bios-trace-v1"
BIOS_EVENT_KINDS = frozenset(
    {"ee_syscall", "exception", "import", "interrupt", "module", "rpc", "timer"}
)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--probe-bios-trace", action="store_true",
                        help="capture the bounded BIOS/IOP census from boot or a savestate")
    parser.add_argument(
        "--probe-bios-phase",
        choices=("menu", "save-load"),
        help="capture a bounded BIOS/IOP phase after a menu action or save/load; requires --statefile",
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

    for expected_sequence, event in enumerate(events, start=1):
        if not isinstance(event, dict) \
                or event.get("sequence") != expected_sequence \
                or not isinstance(event.get("kind"), str) \
                or event["kind"] not in BIOS_EVENT_KINDS:
            return False
        calls = event.get("calls", 1)
        if isinstance(calls, bool) or not isinstance(calls, int) or calls <= 0:
            return False
    return True


def bios_trace_failure_detail(trace: object) -> str:
    if not isinstance(trace, dict):
        return f"response is not an object ({type(trace).__name__})"
    events = trace.get("events")
    event_count = len(events) if isinstance(events, list) else "invalid"
    return (
        f"schema={trace.get('schema')!r} enabled={trace.get('enabled')!r} "
        f"events={event_count} overflow={trace.get('overflow')!r}"
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


def prepare_bios_trace_for_native_stream(port: int, enabled: bool) -> None:
    if enabled:
        start_bios_trace(port)


def run_bios_phase(
    port: int,
    deadline: float,
    phase: str,
    statefile: Path,
    state_path: Path,
) -> tuple[dict[str, object], str, str]:
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
    if trace is None:
        detail = probe_error or "probe did not run"
        print(f"FATAL BIOS trace failed: {detail}; see {log_dir}", file=sys.stderr)
        return False
    actual_output = output or (log_dir.parent / "bios-trace.json")
    write_bios_trace(trace, actual_output, control_status, statefile, phase, operation)
    print(f"control-test bios-trace output={actual_output}", flush=True)
    return True
