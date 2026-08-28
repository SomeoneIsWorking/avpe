"""Surfaceless BIOS/IOP census polling and proof policy."""

import argparse
import json
import sys
from pathlib import Path

from avpe.control_http import request_bytes

BIOS_TRACE_SCHEMA = "avpe-bios-trace-v1"
BIOS_EVENT_KINDS = frozenset(
    {"ee_syscall", "exception", "import", "interrupt", "module", "rpc", "timer"}
)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--probe-bios-trace", action="store_true",
                        help="capture the bounded BIOS/IOP census from a clean boot")
    parser.add_argument("--bios-trace-output", type=Path,
                        help="write --probe-bios-trace JSON to this scratch path")


def validate_arguments(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.probe_bios_trace and args.statefile is not None:
        parser.error("--probe-bios-trace requires a clean boot without --statefile")
    if args.bios_trace_output is not None and not args.probe_bios_trace:
        parser.error("--bios-trace-output requires --probe-bios-trace")


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
    return True


def capture_bios_trace(port: int) -> dict[str, object]:
    status, body = request_bytes(port, "POST", "/bios/trace/capture", {})
    if status != 200:
        raise RuntimeError(f"BIOS trace capture returned HTTP {status}")
    trace = json.loads(body)
    if not bios_trace_is_verified(trace):
        raise RuntimeError(f"complete BIOS trace was not observed: {trace}")
    return trace


def capture_bios_trace_if_requested(
    enabled: bool, port: int, probe_error: str | None
) -> tuple[dict[str, object] | None, str | None]:
    if not enabled or probe_error is not None:
        return None, None
    try:
        return capture_bios_trace(port), None
    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
        return None, str(error)


def write_bios_trace(
    trace: dict[str, object],
    output: Path,
    control_status: dict[str, object],
) -> None:
    artifact = {
        "phase": "clean_boot_to_running",
        "control_status": control_status,
        "trace": trace,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")


def report_bios_trace(
    trace: dict[str, object] | None,
    output: Path | None,
    control_status: dict[str, object],
    log_dir: Path,
) -> bool:
    if trace is None:
        print("FATAL BIOS trace failed; see " + str(log_dir), file=sys.stderr)
        return False
    actual_output = output or (log_dir.parent / "bios-trace.json")
    write_bios_trace(trace, actual_output, control_status)
    print(f"control-test bios-trace output={actual_output}", flush=True)
    return True
