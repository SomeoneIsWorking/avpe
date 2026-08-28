"""Shared typed-menu diagnostic calls for surfaceless AVP:E probes."""

import json
import time

from avpe.control_http import request_bytes, request_json


def menu_action(
    port: int,
    action: str,
) -> tuple[int, dict[str, object] | None, str]:
    return request_json(port, "POST", "/input/menu-action", {"action": action})


def menu_state(port: int) -> tuple[int, dict[str, object] | None, str]:
    status, body = request_bytes(port, "GET", "/input/menu")
    detail = body.decode(errors="replace").strip()
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return status, None, detail
    return status, parsed if isinstance(parsed, dict) else None, detail


def await_deferred_call(
    port: int,
    deadline: float,
    call_id: int,
    description: str,
) -> dict[str, object]:
    completion: dict[str, object] | None = None
    while time.monotonic() < deadline:
        status, body = request_bytes(port, "GET", "/ee/deferred")
        if status != 200:
            raise RuntimeError(f"deferred status returned HTTP {status}")
        candidate = json.loads(body)
        if not isinstance(candidate, dict) or int(candidate.get("id", 0)) != call_id:
            raise RuntimeError(
                f"deferred status did not identify call {call_id}: {candidate}"
            )
        if candidate.get("state") in ("completed", "failed"):
            completion = candidate
            break
        time.sleep(0.05)
    if not deferred_completion_is_safe(completion):
        raise RuntimeError(
            f"deferred {description} did not complete safely: {completion}"
        )
    assert completion is not None
    return completion


def run_deferred_menu_action(
    port: int,
    deadline: float,
    action: str,
) -> tuple[dict[str, object], dict[str, object]]:
    status, response, detail = menu_action(port, action)
    if (
        status != 202
        or response is None
        or response.get("deferred") is not True
        or _integer(response.get("deferred_call_id")) <= 0
    ):
        raise RuntimeError(
            f"native menu {action} was not queued through deferred execution: "
            f"HTTP {status}: {detail}"
        )
    call_id = _integer(response["deferred_call_id"])
    completion = await_deferred_call(port, deadline, call_id, f"menu {action}")
    return response, completion


def deferred_completion_is_safe(value: object) -> bool:
    return bool(
        isinstance(value, dict)
        and value.get("state") == "completed"
        and value.get("succeeded") is True
        and value.get("stack_restored") is True
        and value.get("staging_address") != "0x00000000"
    )


def _integer(value: object) -> int:
    if isinstance(value, bool):
        return -1
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return -1
