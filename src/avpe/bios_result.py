"""Strict validation for bounded BIOS/IOP result summaries."""


def event_result_is_verified(
    event: dict[str, object],
    result_valid: bool,
    allows_u64: bool,
    calls: int,
) -> bool:
    has_summary = "result_summary" in event
    if "result" in event or "result_u64" in event:
        return False
    if not result_valid:
        return not has_summary
    if not has_summary:
        return False
    summary = event["result_summary"]
    if not isinstance(summary, dict) or set(summary) != {
        "encoding", "first", "last", "min", "max", "changes"
    }:
        return False
    encoding = summary["encoding"]
    minimum = summary["min"]
    maximum = summary["max"]
    first = summary["first"]
    last = summary["last"]
    changes = summary["changes"]
    if encoding not in {"s32", "u64"} or (encoding == "u64" and not allows_u64):
        return False
    lower = 0 if encoding == "u64" else -(1 << 31)
    upper = (1 << 64) if encoding == "u64" else (1 << 31)
    if any(
        isinstance(value, bool) or not isinstance(value, int)
        or not lower <= value < upper
        for value in (first, last, minimum, maximum)
    ):
        return False
    if isinstance(changes, bool) or not isinstance(changes, int) \
            or not 0 <= changes < calls:
        return False
    if not minimum <= first <= maximum or not minimum <= last <= maximum:
        return False
    return (changes == 0) == (minimum == maximum)
