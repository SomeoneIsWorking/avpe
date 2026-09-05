"""Validation and identity-preserving summaries of exception and counter events."""

from typing import Any


IDENTITY_FIELDS = {
    "exception": ("domain", "code", "pc", "branch_delay"),
    "timer": ("domain", "counter", "overflow", "delivered"),
}
EXCEPTION_TRANSITION_FIELDS = (
    "status_before", "status_after", "cause_after", "epc_after", "vector_pc",
)


def event_occurrences(event: dict[str, Any]) -> int:
    calls = event.get("calls", 1)
    if not isinstance(calls, int) or isinstance(calls, bool) or calls <= 0:
        raise ValueError("BIOS event occurrences must be a positive integer")
    return calls


def _unsigned(value: object, bits: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 1 << bits


def runtime_event_is_verified(event: dict[str, object]) -> bool:
    """Accept only the fields actually emitted by the shared CPU/counter owners."""
    if event.get("domain") not in ("ee", "iop"):
        return False
    if event.get("kind") == "exception":
        transition = event.get("transition")
        return bool(
            all(_unsigned(event.get(key), 32) for key in ("code", "pc"))
            and isinstance(event.get("branch_delay"), bool)
            and isinstance(transition, dict)
            and set(transition) == set(EXCEPTION_TRANSITION_FIELDS)
            and all(_unsigned(transition[key], 32) for key in EXCEPTION_TRANSITION_FIELDS)
        )
    if event.get("kind") == "timer":
        return bool(
            _unsigned(event.get("counter"), 32)
            and all(_unsigned(event.get(key), 64) for key in ("count", "target", "cycle"))
            and all(isinstance(event.get(key), bool) for key in ("overflow", "delivered"))
        )
    return False


def summarize_runtime_events(events: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    """Keep joint identities and occurrence counts, not uncorrelated marginal totals.

    Timer samples are the first samples retained by the sink, never min/max,
    elapsed time or per-occurrence measurements. `delivered` means assertion
    at the timer interrupt source, not CPU exception or BIOS handler entry.
    """
    fields = IDENTITY_FIELDS[kind]
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    event_count = 0
    occurrences = 0
    for event in events:
        if event["kind"] != kind:
            continue
        if not runtime_event_is_verified(event):
            raise ValueError(f"invalid {kind} event")
        calls = event_occurrences(event)
        key = tuple(event[field] for field in fields)
        if kind == "exception":
            key += tuple(event["transition"][field] for field in EXCEPTION_TRANSITION_FIELDS)
        if key not in grouped:
            entry = {field: event[field] for field in fields}
            entry.update(event_count=0, occurrences=0)
            if kind == "exception":
                entry["transition"] = dict(event["transition"])
            if kind == "timer":
                entry["first_sample"] = {field: event[field] for field in ("count", "target", "cycle")}
            grouped[key] = entry
        grouped[key]["event_count"] += 1
        grouped[key]["occurrences"] += calls
        event_count += 1
        occurrences += calls
    return {
        "event_count": event_count, "occurrences": occurrences,
        "measurement": "cpu_exception_transition" if kind == "exception" else "counter_source_irq_assertion",
        "identities": [grouped[key] for key in sorted(grouped)],
    }
