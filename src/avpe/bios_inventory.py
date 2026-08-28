"""Deterministic summaries for captured AVP:E BIOS/IOP trace artifacts."""

from __future__ import annotations

from collections import Counter
from typing import Any

from avpe.native_bios_probe import bios_trace_is_verified


INVENTORY_SCHEMA = "avpe-bios-inventory-v1"
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
        "exceptions": _summarize_exceptions(events),
        "timers": _summarize_timers(events),
    }

    for kind in _SERVICE_KINDS:
        summary["services"][kind] = _summarize_services(events, kind)
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
        entry["calls"] = entry.get("calls", 0) + 1
        if kind == "ee_syscall" or kind == "import":
            entry.setdefault("results", set()).add(_required_int(event, "result"))
        if kind == "module":
            entry.setdefault("operations", set()).add(_required_string(event, "operation"))
        if kind == "interrupt":
            entry.setdefault("handlers", set()).add(_required_int(event, "handler"))

    result = []
    for entry in grouped.values():
        for key in ("results", "operations", "handlers"):
            if key in entry:
                entry[key] = sorted(entry[key])
        result.append(entry)
    return sorted(
        result,
        key=lambda entry: tuple(
            str(entry[key]) for key in entry if key != "calls"
        ),
    )


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
            ("hle", _required_bool(event, "hle")),
            ("debug", _required_bool(event, "debug")),
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


def _summarize_exceptions(events: list[dict[str, Any]]) -> dict[str, Any]:
    exceptions = [event for event in events if event["kind"] == "exception"]
    return {
        "count": len(exceptions),
        "domains": dict(
            sorted(
                Counter(_required_string(event, "domain") for event in exceptions).items()
            )
        ),
        "codes": dict(
            sorted(
                Counter(str(_required_int(event, "code")) for event in exceptions).items()
            )
        ),
        "pcs": dict(
            sorted(
                Counter(str(_required_int(event, "pc")) for event in exceptions).items()
            )
        ),
    }


def _summarize_timers(events: list[dict[str, Any]]) -> dict[str, Any]:
    timers = [event for event in events if event["kind"] == "timer"]
    return {
        "count": len(timers),
        "domains": dict(
            sorted(Counter(_required_string(event, "domain") for event in timers).items())
        ),
        "counters": dict(
            sorted(
                Counter(str(_required_int(event, "counter")) for event in timers).items()
            )
        ),
        "overflow": dict(
            sorted(
                Counter(
                    str(_required_bool(event, "overflow")).lower()
                    for event in timers
                ).items()
            )
        ),
        "delivered": dict(
            sorted(
                Counter(
                    str(_required_bool(event, "delivered")).lower()
                    for event in timers
                ).items()
            )
        ),
    }


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


def _required_bool(event: dict[str, Any], key: str) -> bool:
    value = event.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"BIOS event field {key!r} must be a boolean")
    return value
