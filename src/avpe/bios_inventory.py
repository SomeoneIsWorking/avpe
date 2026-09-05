"""Deterministic summaries for captured AVP:E BIOS/IOP trace artifacts."""

from __future__ import annotations

from collections import Counter
from typing import Any

from avpe.native_bios_probe import bios_trace_is_verified
from avpe.bios_runtime_events import event_occurrences as _event_calls, summarize_runtime_events


INVENTORY_SCHEMA = "avpe-bios-inventory-v6"
_SERVICE_KINDS = ("ee_syscall", "import", "module", "interrupt", "rpc")


def summarize_bios_artifact(artifact: object) -> dict[str, Any]:
    """Return a stable, semantic summary of one validated trace artifact.

    The event sink remains the source of truth. This function only groups the
    already captured events and never infers an unobserved service call.
    """

    if not isinstance(artifact, dict):
        raise ValueError("BIOS artifact must be an object")
    trace = artifact.get("trace")
    if not bios_trace_is_verified(trace):
        raise ValueError("BIOS artifact contains an invalid or incomplete trace")
    events = trace["events"]

    summary: dict[str, Any] = {
        "schema": INVENTORY_SCHEMA,
        "phase": _optional_string(artifact, "phase"),
        "operation": _optional_string(artifact, "operation"),
        "statefile": _optional_string(artifact, "statefile"),
        "event_count": len(events),
        "event_counts": dict(
            sorted(Counter(event["kind"] for event in events).items())
        ),
        "services": {kind: [] for kind in _SERVICE_KINDS},
        "exceptions": summarize_runtime_events(events, "exception"),
        "timers": summarize_runtime_events(events, "timer"),
    }

    for kind in _SERVICE_KINDS:
        if kind == "ee_syscall":
            services = _summarize_ee_syscalls(events)
        elif kind == "import":
            services = _summarize_iop_imports(events)
        else:
            services = _summarize_services(events, kind)
        summary["services"][kind] = services
    return summary


def combine_bios_inventories(
    inventories: list[dict[str, Any]],
) -> dict[str, Any]:
    """Combine summaries without discarding capture-level provenance."""

    if not inventories:
        raise ValueError("at least one BIOS inventory is required")
    if any(inventory.get("schema") != INVENTORY_SCHEMA for inventory in inventories):
        raise ValueError("BIOS inventory schema mismatch")

    event_counts: Counter[str] = Counter()
    phases: set[str] = set()
    service_kinds: set[str] = set()
    for inventory in inventories:
        event_counts.update(inventory["event_counts"])
        phase = inventory.get("phase")
        if phase is not None:
            phases.add(phase)
        service_kinds.update(
            kind for kind, services in inventory["services"].items() if services
        )

    return {
        "schema": INVENTORY_SCHEMA,
        "capture_count": len(inventories),
        "phases": sorted(phases),
        "event_counts": dict(sorted(event_counts.items())),
        "service_kinds": sorted(service_kinds),
    }


def _optional_string(mapping: dict[str, Any], key: str) -> str | None:
    value = mapping.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"BIOS artifact field {key!r} must be a string")
    return value


def _summarize_services(events: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for event in events:
        if event["kind"] != kind:
            continue
        identity = _service_identity(event, kind)
        entry = grouped.setdefault(
            identity,
            {key: value for key, value in _identity_fields(event, kind)},
        )
        calls = _event_calls(event)
        entry["calls"] = entry.get("calls", 0) + calls
        if kind == "module":
            entry.setdefault("operations", set()).add(_required_string(event, "operation"))
        if kind == "interrupt":
            entry.setdefault("handlers", set()).add(_required_int(event, "handler"))

    result = []
    for entry in grouped.values():
        for key in ("operations", "handlers"):
            if key in entry:
                entry[key] = sorted(entry[key])
        if "outcomes" in entry:
            entry["outcomes"] = dict(sorted(entry["outcomes"].items()))
            entry.setdefault("observed_result_calls", 0)
            entry.setdefault("unobserved_result_calls", 0)
        result.append(entry)
    return sorted(
        result,
        key=lambda entry: tuple(
            str(entry[key]) for key in entry if key != "calls"
        ),
    )


def _summarize_iop_imports(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    oracle_entry_calls: Counter[tuple[Any, ...]] = Counter()
    oracle_return_calls: Counter[tuple[Any, ...]] = Counter()
    for event in events:
        if event["kind"] != "import":
            continue
        identity = _service_identity(event, "import")
        entry = grouped.setdefault(
            identity,
            {key: value for key, value in _identity_fields(event, "import")},
        )
        calls = _event_calls(event)
        entry["calls"] = entry.get("calls", 0) + calls
        outcome = _required_string(event, "outcome")
        entry.setdefault("outcomes", Counter())[outcome] += calls
        if outcome == "oracle":
            oracle_entry_calls[identity] += calls
        else:
            entry["observed_result_calls"] = (
                entry.get("observed_result_calls", 0) + calls
            )
            _merge_result_observations(entry, event)

    for event in events:
        if event["kind"] != "iop_import_return":
            continue
        identity = _service_identity(event, "import")
        entry = grouped.get(identity)
        if entry is None:
            raise ValueError("IOP import return has no matching entry identity")
        calls = _event_calls(event)
        oracle_return_calls[identity] += calls
        entry["returned_oracle_calls"] = entry.get("returned_oracle_calls", 0) + calls
        entry["observed_result_calls"] = entry.get("observed_result_calls", 0) + calls
        _merge_result_observations(entry, event)

    result = []
    for identity, entry in grouped.items():
        pending_calls = oracle_entry_calls[identity] - oracle_return_calls[identity]
        if pending_calls < 0:
            raise ValueError("IOP oracle returns exceed matching entries")
        entry["outcomes"] = dict(sorted(entry["outcomes"].items()))
        _finalize_result_observations(entry)
        entry.setdefault("observed_result_calls", 0)
        entry["unobserved_result_calls"] = pending_calls
        entry.setdefault("returned_oracle_calls", 0)
        result.append(entry)
    return sorted(
        result,
        key=lambda entry: (
            entry["library"],
            entry["ordinal"],
            entry["function"],
            entry["hle_available"],
            entry["debug_available"],
        ),
    )


def _summarize_ee_syscalls(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    bios_entry_calls: Counter[tuple[Any, ...]] = Counter()
    bios_result_entry_calls: Counter[tuple[Any, ...]] = Counter()
    bios_result_return_calls: Counter[tuple[Any, ...]] = Counter()
    for event in events:
        if event["kind"] != "ee_syscall":
            continue
        identity = _service_identity(event, "ee_syscall")
        entry = grouped.setdefault(
            identity,
            {key: value for key, value in _identity_fields(event, "ee_syscall")},
        )
        calls = _event_calls(event)
        entry["calls"] = entry.get("calls", 0) + calls
        outcome = _required_string(event, "outcome")
        result_expected = _required_bool(event, "result_expected")
        return_expected = _required_bool(event, "return_expected")
        entry.setdefault("outcomes", Counter())[outcome] += calls
        if outcome == "bios" and return_expected:
            bios_entry_calls[identity] += calls
            if result_expected:
                bios_result_entry_calls[identity] += calls
        elif outcome == "bios":
            entry["nonreturning_calls"] = entry.get("nonreturning_calls", 0) + calls
        elif _required_bool(event, "result_valid"):
            entry["observed_result_calls"] = entry.get("observed_result_calls", 0) + calls
            _merge_result_observations(entry, event)
        elif result_expected:
            entry["unobserved_result_calls"] = (
                entry.get("unobserved_result_calls", 0) + calls
            )
        else:
            entry["resultless_calls"] = entry.get("resultless_calls", 0) + calls

    for event in events:
        if event["kind"] != "ee_syscall_return":
            continue
        identity = _service_identity(event, "ee_syscall")
        entry = grouped.get(identity)
        if entry is None:
            raise ValueError("BIOS syscall return has no matching entry identity")
        calls = _event_calls(event)
        entry["returned_bios_calls"] = entry.get("returned_bios_calls", 0) + calls
        result_expected = _required_bool(event, "result_expected")
        result_valid = _required_bool(event, "result_valid")
        if result_expected:
            bios_result_return_calls[identity] += calls
        if result_valid:
            entry["observed_result_calls"] = entry.get("observed_result_calls", 0) + calls
            _merge_result_observations(entry, event)
        elif result_expected:
            entry["unobserved_result_calls"] = (
                entry.get("unobserved_result_calls", 0) + calls
            )
        else:
            entry["resultless_calls"] = entry.get("resultless_calls", 0) + calls

    result = []
    for identity, entry in grouped.items():
        returned_calls = entry.get("returned_bios_calls", 0)
        if returned_calls > bios_entry_calls[identity]:
            raise ValueError("BIOS syscall returns exceed matching entries")
        pending_result_calls = (
            bios_result_entry_calls[identity] - bios_result_return_calls[identity]
        )
        if pending_result_calls < 0:
            raise ValueError("BIOS syscall result returns exceed matching entries")
        entry["unobserved_result_calls"] = (
            entry.get("unobserved_result_calls", 0) + pending_result_calls
        )
        entry["outcomes"] = dict(sorted(entry["outcomes"].items()))
        _finalize_result_observations(entry)
        entry.setdefault("observed_result_calls", 0)
        entry.setdefault("returned_bios_calls", 0)
        entry.setdefault("resultless_calls", 0)
        entry.setdefault("nonreturning_calls", 0)
        result.append(entry)
    return sorted(result, key=lambda entry: (entry["number"], entry["name"]))


def _service_identity(event: dict[str, Any], kind: str) -> tuple[Any, ...]:
    return tuple(value for _, value in _identity_fields(event, kind))


def _identity_fields(event: dict[str, Any], kind: str) -> list[tuple[str, Any]]:
    if kind == "ee_syscall":
        return [
            ("number", _required_int(event, "number")),
            ("name", _required_string(event, "name")),
        ]
    if kind == "import":
        return [
            ("library", _required_string(event, "library")),
            ("ordinal", _required_int(event, "ordinal")),
            ("function", _required_string(event, "function")),
            ("hle_available", _required_bool(event, "hle_available")),
            ("debug_available", _required_bool(event, "debug_available")),
        ]
    if kind == "module":
        return [
            ("module", _required_string(event, "module")),
            ("version_major", _required_int(event, "version_major")),
            ("version_minor", _required_int(event, "version_minor")),
        ]
    if kind == "interrupt":
        return [
            ("number", _required_int(event, "number")),
            ("name", _required_string(event, "name")),
        ]
    if kind == "rpc":
        return [("rpc_id", _required_int(event, "rpc_id"))]
    raise ValueError(f"unsupported BIOS service kind: {kind}")


def _required_string(event: dict[str, Any], key: str) -> str:
    value = event.get(key)
    if not isinstance(value, str):
        raise ValueError(f"BIOS event field {key!r} must be a string")
    return value


def _required_int(event: dict[str, Any], key: str) -> int:
    value = event.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"BIOS event field {key!r} must be an integer")
    return value


def _required_result_summary(event: dict[str, Any]) -> dict[str, Any]:
    summary = event.get("result_summary")
    if not isinstance(summary, dict):
        raise ValueError("BIOS event must carry a result summary")
    return summary


def _merge_result_observations(
    entry: dict[str, Any], event: dict[str, Any]
) -> None:
    summary = _required_result_summary(event)
    encoding = _required_string(summary, "encoding")
    first = _required_int(summary, "first")
    last = _required_int(summary, "last")
    minimum = _required_int(summary, "min")
    maximum = _required_int(summary, "max")
    changes = _required_int(summary, "changes")
    observations = entry.get("result_observations")
    if observations is None:
        observations = {
            "encoding": encoding,
            "samples": set(),
            "min": minimum,
            "max": maximum,
            "transitions_within_trace_events": 0,
        }
        entry["result_observations"] = observations
    elif observations["encoding"] != encoding:
        raise ValueError("BIOS service mixes result encodings")
    observations["samples"].update((first, last, minimum, maximum))
    observations["min"] = min(observations["min"], minimum)
    observations["max"] = max(observations["max"], maximum)
    observations["transitions_within_trace_events"] += changes


def _finalize_result_observations(entry: dict[str, Any]) -> None:
    observations = entry.get("result_observations")
    if observations is None:
        entry["result_observations"] = None
        return
    observations["samples"] = sorted(observations["samples"])


def _required_bool(event: dict[str, Any], key: str) -> bool:
    value = event.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"BIOS event field {key!r} must be a boolean")
    return value
